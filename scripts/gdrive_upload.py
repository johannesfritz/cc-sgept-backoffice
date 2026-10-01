#!/usr/bin/env python3
"""Google Drive upload backend: Google Drive API v3 on every platform.

Uses the service account at claude-setup/mcp-google-workspace/service-account.json.
The Drive for desktop folder is never read: it can list a stale subset of the
invoice folders and so cannot be trusted for folder reuse.

Overwrite-in-place semantics:
  - A folder whose name ends in ' {invoice_number}' is reused if present.
    Otherwise a new folder 'YYMMDD [NIPO ]{ABBREV} {NUMBER}' is created.
  - Any existing SGEPT-invoice{NUMBER}.* files in that folder are deleted
    before the fresh copies are placed. No version drift.
"""

from __future__ import annotations

import mimetypes
import sys
from datetime import datetime
from pathlib import Path


GDRIVE_FOLDER_ID_ROOT = "19bPRghIb2L3cdxZzIattO65uM5En6dHM"

# The mcp-google-workspace service account credential.
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
    """Upload .docx + .pdf to the Drive invoicing folder through the Drive API.

    Returns the URL of the Drive folder.
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

    return _sync_api(docx_path, pdf_path, inv_num, abbrev, is_nipo)


# ------------------------------------------------------------ Drive listing

def list_invoice_folders() -> list[str]:
    """Return the names of all non-trashed folders directly under the Drive invoicing folder.

    Reads every result page through the Drive API with the service account,
    on every platform. Read-only: nothing in Drive is changed.
    """
    if not SERVICE_ACCOUNT_PATH.exists():
        raise FileNotFoundError(
            f"Drive service account credential not found: {SERVICE_ACCOUNT_PATH}"
        )

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_PATH), scopes=DRIVE_SCOPES,
    ).with_subject(DRIVE_IMPERSONATE_SUBJECT)
    drive = build('drive', 'v3', credentials=creds, cache_discovery=False)

    query = (
        f"'{GDRIVE_FOLDER_ID_ROOT}' in parents and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    names: list[str] = []
    page_token = None
    while True:
        res = drive.files().list(
            q=query, fields="nextPageToken, files(name)", pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True, includeItemsFromAllDrives=True,
        ).execute()
        names.extend(f['name'] for f in res.get('files', []))
        page_token = res.get('nextPageToken')
        if not page_token:
            return names


# ----------------------------------------------------------------- Drive API

def _open_drive():
    """Return a Drive v3 service for the service account, impersonating the invoicing owner."""
    if not SERVICE_ACCOUNT_PATH.exists():
        raise FileNotFoundError(
            f"Drive service account credential not found: {SERVICE_ACCOUNT_PATH}"
        )

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_PATH), scopes=DRIVE_SCOPES,
    ).with_subject(DRIVE_IMPERSONATE_SUBJECT)
    return build('drive', 'v3', credentials=creds, cache_discovery=False)


def _reuse_or_create_folder(drive, inv_num: str, abbrev: str, is_nipo: bool) -> tuple[str, str]:
    """Return (folder id, folder name) of the Drive folder ending in ' {inv_num}', creating it if absent."""
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
        return candidates[0]['id'], candidates[0]['name']

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
    return folder['id'], folder_name


def upload_invoice_files(inv_num: str, abbrev: str, is_nipo: bool, paths: list[Path]) -> str:
    """Upload files under their own names into the Drive folder for inv_num; return the folder URL.

    Reuses the folder ending in ' {inv_num}' or creates 'YYMMDD [NIPO ]{abbrev} {inv_num}'.
    Unlike _sync_api, nothing already in the folder is deleted or renamed.
    """
    from googleapiclient.http import MediaFileUpload

    drive = _open_drive()
    folder_id, folder_name = _reuse_or_create_folder(drive, inv_num, abbrev, is_nipo)
    for path in paths:
        mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        drive.files().create(
            body={'name': path.name, 'parents': [folder_id]},
            media_body=MediaFileUpload(str(path), mimetype=mime, resumable=False),
            fields='id, name',
            supportsAllDrives=True,
        ).execute()
    url = f"https://drive.google.com/drive/folders/{folder_id}"
    print(f"\nUploaded to Google Drive (API): {folder_name} ({url})")
    return url


def _sync_api(
    docx_path: Path, pdf_path: Path, inv_num: str, abbrev: str, is_nipo: bool,
) -> str:
    """Reuse or create the Drive folder for inv_num, replace its SGEPT-invoice files, return its URL."""
    from googleapiclient.http import MediaFileUpload

    drive = _open_drive()
    folder_id, folder_name = _reuse_or_create_folder(drive, inv_num, abbrev, is_nipo)

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
