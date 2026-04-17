#!/usr/bin/env python3
"""Google Drive upload backend: cross-platform dispatcher.

macOS -> Drive File Stream mount (filesystem copy).
Linux -> Google Drive API v3 using the service account at
         claude-setup/mcp-google-workspace/service-account.json.

Overwrite-in-place semantics on both backends:
  - A folder whose name ends in ' {invoice_number}' is reused if present.
    Otherwise a new folder 'YYMMDD [NIPO ]{ABBREV} {NUMBER}' is created.
  - Any existing SGEPT-invoice{NUMBER}.* files in that folder are deleted
    before the fresh copies are placed. No version drift.
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path


GDRIVE_FOLDER_ID_ROOT = "19bPRghIb2L3cdxZzIattO65uM5En6dHM"

# macOS mount of Drive File Stream
GDRIVE_INVOICING_MAC = Path(
    "/Users/johannesfritz/Library/CloudStorage/GoogleDrive-johannes.fritz@sgept.org/"
    "Meine Ablage/SGEPT ORG/SGEPT admin/dbx/SGEPT/0 admin/5 invoicing"
)

# Linux: expect the mcp-google-workspace service account credential.
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
_CLAUDE_SETUP_ROOT = _REPO_ROOT.parent
SERVICE_ACCOUNT_PATH = _CLAUDE_SETUP_ROOT / "mcp-google-workspace" / "service-account.json"

DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]

# The "5 invoicing" folder lives in johannes.fritz@sgept.org's Drive.
# The service account has domain-wide delegation; impersonate the owner
# (mirrors how mcp-google-workspace already impersonates for Gmail/Calendar).
DRIVE_IMPERSONATE_SUBJECT = "johannes.fritz@sgept.org"


def sync_to_gdrive(
    invoice_number,
    abbrev,
    is_nipo=False,
    docx_path=None,
    output_dir=None,
):
    """Upload .docx + .pdf to the Drive invoicing folder. Returns destination descriptor.

    On macOS the return is the local Path to the destination folder.
    On Linux the return is a string URL to the Drive folder.
    """
    inv_num = str(invoice_number).replace('-', '').strip()

    # Locate local source .docx
    if docx_path is None:
        if output_dir is None:
            raise ValueError("output_dir is required when docx_path is not given.")
        output_dir = Path(output_dir)
        candidates = sorted(output_dir.rglob(f"Invoice-{inv_num}-*.docx"))
        if not candidates:
            raise FileNotFoundError(
                f"No local source found: {output_dir}/**/Invoice-{inv_num}-*.docx"
            )
        docx_path = max(candidates, key=lambda p: p.stat().st_mtime)
    docx_path = Path(docx_path)
    if not docx_path.exists():
        raise FileNotFoundError(f"Source .docx not found: {docx_path}")

    # Ensure PDF exists and is fresh.
    pdf_path = docx_path.with_suffix('.pdf')
    if not pdf_path.exists() or pdf_path.stat().st_mtime < docx_path.stat().st_mtime:
        sys.path.insert(0, str(_SCRIPT_DIR))
        from pdf_convert import convert_to_pdf
        pdf_path = convert_to_pdf(docx_path)

    if sys.platform == 'darwin':
        return _sync_macos(docx_path, pdf_path, inv_num, abbrev, is_nipo)
    if sys.platform.startswith('linux'):
        return _sync_linux(docx_path, pdf_path, inv_num, abbrev, is_nipo)
    raise RuntimeError(f"Unsupported platform for Drive sync: {sys.platform}")


# --------------------------------------------------------------------- macOS

def _sync_macos(docx_path, pdf_path, inv_num, abbrev, is_nipo):
    if not GDRIVE_INVOICING_MAC.exists():
        raise FileNotFoundError(
            f"Google Drive mount not available: {GDRIVE_INVOICING_MAC}. "
            "Is the Drive File Stream client running?"
        )

    existing = [
        p for p in GDRIVE_INVOICING_MAC.iterdir()
        if p.is_dir() and p.name.endswith(f" {inv_num}")
    ]
    if existing:
        dest_folder = existing[0]
    else:
        date_prefix = datetime.now().strftime('%y%m%d')
        type_token = 'NIPO ' if is_nipo else ''
        dest_folder = GDRIVE_INVOICING_MAC / f"{date_prefix} {type_token}{abbrev} {inv_num}"
        dest_folder.mkdir(parents=True, exist_ok=False)

    for stale in dest_folder.glob(f"SGEPT-invoice{inv_num}.*"):
        stale.unlink()

    shutil.copy2(docx_path, dest_folder / f"SGEPT-invoice{inv_num}.docx")
    shutil.copy2(pdf_path, dest_folder / f"SGEPT-invoice{inv_num}.pdf")

    print(f"\nSynced to Google Drive (File Stream): {dest_folder}")
    return dest_folder


# --------------------------------------------------------------------- Linux

def _sync_linux(docx_path, pdf_path, inv_num, abbrev, is_nipo):
    if not SERVICE_ACCOUNT_PATH.exists():
        raise FileNotFoundError(
            f"Drive service account credential not found: {SERVICE_ACCOUNT_PATH}"
        )

    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_PATH), scopes=DRIVE_SCOPES,
    ).with_subject(DRIVE_IMPERSONATE_SUBJECT)
    drive = build('drive', 'v3', credentials=creds, cache_discovery=False)

    # Find a folder under the root whose name ends with ' {inv_num}'.
    q = (
        f"'{GDRIVE_FOLDER_ID_ROOT}' in parents and "
        f"mimeType = 'application/vnd.google-apps.folder' and "
        f"name contains '{inv_num}' and trashed = false"
    )
    res = drive.files().list(
        q=q, fields="files(id, name)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    candidates = [f for f in res.get('files', []) if f['name'].endswith(f" {inv_num}")]

    if candidates:
        folder_id = candidates[0]['id']
        folder_name = candidates[0]['name']
    else:
        date_prefix = datetime.now().strftime('%y%m%d')
        type_token = 'NIPO ' if is_nipo else ''
        folder_name = f"{date_prefix} {type_token}{abbrev} {inv_num}"
        folder = drive.files().create(
            body={
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [GDRIVE_FOLDER_ID_ROOT],
            },
            fields='id, name',
            supportsAllDrives=True,
        ).execute()
        folder_id = folder['id']

    # Delete any stale SGEPT-invoice{inv_num}.* files in that folder.
    stale_q = (
        f"'{folder_id}' in parents and trashed = false and "
        f"(name = 'SGEPT-invoice{inv_num}.docx' or name = 'SGEPT-invoice{inv_num}.pdf')"
    )
    stale_res = drive.files().list(
        q=stale_q, fields="files(id, name)",
        supportsAllDrives=True, includeItemsFromAllDrives=True,
    ).execute()
    for f in stale_res.get('files', []):
        drive.files().delete(fileId=f['id'], supportsAllDrives=True).execute()

    # Upload docx + pdf.
    for local_path, mime in [
        (docx_path, 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
        (pdf_path, 'application/pdf'),
    ]:
        media = MediaFileUpload(str(local_path), mimetype=mime, resumable=False)
        drive.files().create(
            body={
                'name': f"SGEPT-invoice{inv_num}{local_path.suffix}",
                'parents': [folder_id],
            },
            media_body=media,
            fields='id, name',
            supportsAllDrives=True,
        ).execute()

    url = f"https://drive.google.com/drive/folders/{folder_id}"
    print(f"\nSynced to Google Drive (API): {folder_name} ({url})")
    return url


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Upload SGEPT invoice to Google Drive")
    ap.add_argument('--number', required=True, help="5-digit invoice number")
    ap.add_argument('--abbrev', required=True, help="Short client abbreviation")
    ap.add_argument('--nipo', action='store_true', help="Include 'NIPO' in folder name")
    ap.add_argument('--docx', type=Path, required=True, help="Source .docx path")
    args = ap.parse_args()
    out = sync_to_gdrive(args.number, args.abbrev, is_nipo=args.nipo, docx_path=args.docx)
    print(f"DRIVE_OUTPUT: {out}")
