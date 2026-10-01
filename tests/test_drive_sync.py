"""Acceptance test for the macOS Drive sync (plan invoice-numbering-drive).

The Drive for desktop folder on the Mac showed 6 of 142 invoice folders on
2026-10-01, so the Mac sync must upload through the Drive API like Linux does.
"""
import os
import sys

from conftest import load_script


def test_mac_sync_uploads_through_api_not_mount(tmp_path, monkeypatch):
    gdrive = load_script("gdrive_upload_under_test", "gdrive_upload.py")
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(gdrive, "GDRIVE_INVOICING_MAC", tmp_path / "no-such-mount")
    calls = []

    def fake_api(docx_path, pdf_path, inv_num, abbrev, is_nipo):
        calls.append(inv_num)
        return f"https://drive.google.com/drive/folders/fake-{inv_num}"

    for name in ("_sync_api", "_sync_linux"):
        monkeypatch.setattr(gdrive, name, fake_api, raising=False)

    docx = tmp_path / "Invoice-26999-Test.docx"
    pdf = tmp_path / "Invoice-26999-Test.pdf"
    docx.write_bytes(b"docx")
    pdf.write_bytes(b"pdf")
    os.utime(docx, (1, 1))

    gdrive.sync_to_gdrive("26999", "TEST", docx_path=docx)
    assert calls == ["26999"]
