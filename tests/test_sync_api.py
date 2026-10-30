"""Unit tests for gdrive_upload's Drive API paths against a fake Drive service (no network)."""
import sys
import types
from pathlib import Path

import pytest

from conftest import load_script


class _Call:
    """A Drive request whose execute() returns a canned result."""

    def __init__(self, result: dict) -> None:
        self._result = result

    def execute(self) -> dict:
        return self._result


class FakeFiles:
    """Records files().list/create/delete calls over one existing invoice folder."""

    def __init__(self, folder_name: str) -> None:
        self.folder_name = folder_name
        self.events: list[tuple[str, str]] = []

    def list(self, q: str, **_: object) -> _Call:
        if "mimeType" in q:
            return _Call({"files": [{"id": "F1", "name": self.folder_name}]})
        return _Call({"files": [{"id": "OLD1", "name": "SGEPT-invoice26040.docx"}]})

    def delete(self, fileId: str, **_: object) -> _Call:
        self.events.append(("delete", fileId))
        return _Call({})

    def create(self, body: dict, **_: object) -> _Call:
        if body.get("mimeType") == "application/vnd.google-apps.folder":
            self.events.append(("create-folder", body["name"]))
            return _Call({"id": "NEW", "name": body["name"]})
        self.events.append(("upload", body["name"]))
        return _Call({"id": "U", "name": body["name"]})


def _install_fake_google(monkeypatch, files: FakeFiles) -> None:
    """Put stand-ins for the google client libraries into sys.modules."""
    drive = types.SimpleNamespace(files=lambda: files)
    sa = types.ModuleType("google.oauth2.service_account")

    class Creds:
        @classmethod
        def from_service_account_file(cls, *_a, **_k):
            return types.SimpleNamespace(with_subject=lambda _s: None)

    sa.Credentials = Creds
    oauth = types.ModuleType("google.oauth2")
    oauth.service_account = sa
    discovery = types.ModuleType("googleapiclient.discovery")
    discovery.build = lambda *_a, **_k: drive
    http = types.ModuleType("googleapiclient.http")
    http.MediaFileUpload = lambda path, **_k: path
    for name, mod in {
        "google": types.ModuleType("google"), "google.oauth2": oauth,
        "google.oauth2.service_account": sa,
        "googleapiclient": types.ModuleType("googleapiclient"),
        "googleapiclient.discovery": discovery, "googleapiclient.http": http,
    }.items():
        monkeypatch.setitem(sys.modules, name, mod)


def test_sync_api_reuses_folder_and_replaces_files(tmp_path: Path, monkeypatch, moneypenny_report) -> None:
    gdrive = load_script("gdrive_upload_sync_api", "gdrive_upload.py")
    monkeypatch.setattr(gdrive, "SERVICE_ACCOUNT_PATH", tmp_path)  # any existing path
    files = FakeFiles("260911 GTA Interos Inc. 26040")
    _install_fake_google(monkeypatch, files)
    docx, pdf = tmp_path / "a.docx", tmp_path / "a.pdf"
    docx.write_bytes(b"d")
    pdf.write_bytes(b"p")

    url = gdrive._sync_api(docx, pdf, "26040", "OTHER", False)

    assert url.endswith("/F1")
    assert files.events == [
        ("delete", "OLD1"),
        ("upload", "SGEPT-invoice26040.docx"),
        ("upload", "SGEPT-invoice26040.pdf"),
    ]


# moneypenny-before-upload (JF-4429): every upload path refuses a number Moneypenny holds.

def _invoice_files(tmp_path: Path, number: str) -> Path:
    """Write a local .docx with a fresher .pdf beside it, so no conversion runs; return the .docx."""
    docx = tmp_path / f"Invoice-{number}-TEST.docx"
    docx.write_bytes(b"d")
    docx.with_suffix(".pdf").write_bytes(b"p")
    return docx


def test_step_f_upload_refuses_a_number_a_lina_draft_holds(
    tmp_path, monkeypatch, capsys, moneypenny_report, moneypenny_reserved
):
    """The handler's STEP F command uploads nothing and prints Refused when a draft took the number meanwhile."""
    moneypenny_reserved[2026] = ["26047-410210"]
    gdrive = load_script("gdrive_upload_step_f", "gdrive_upload.py")
    monkeypatch.setattr(gdrive, "SERVICE_ACCOUNT_PATH", tmp_path)  # any existing path
    files = FakeFiles("unused")
    _install_fake_google(monkeypatch, files)
    docx = _invoice_files(tmp_path, "26047")
    monkeypatch.setattr(sys, "argv", ["gdrive_upload.py", "--number", "26047", "--abbrev", "TEST", "--docx", str(docx)])
    with pytest.raises(SystemExit) as exit_info:
        gdrive._cli()
    assert exit_info.value.code == 1
    assert "Refused: Invoice number 26047 is held by a Lina draft in Moneypenny as 26047-410210" in capsys.readouterr().err
    assert files.events == []


def _real_drive(monkeypatch, tmp_path: Path, folder_name: str) -> FakeFiles:
    """Put the real gdrive_upload, over a fake Drive service, where the generator imports it; return the fake files."""
    gdrive = load_script("gdrive_upload", "gdrive_upload.py")
    monkeypatch.setattr(gdrive, "SERVICE_ACCOUNT_PATH", tmp_path)  # any existing path
    monkeypatch.setitem(sys.modules, "gdrive_upload", gdrive)
    files = FakeFiles(folder_name)
    _install_fake_google(monkeypatch, files)
    return files


def test_invoice_gdrive_sync_refuses_a_number_moneypenny_issued(tmp_path, monkeypatch, generator, moneypenny_issued):
    """/invoice-gdrive-sync, through the generator's sync_to_gdrive, changes nothing on Drive."""
    moneypenny_issued[2026] = ["26047"]
    files = _real_drive(monkeypatch, tmp_path, "261027 TEST 26047")
    docx = _invoice_files(generator.OUTPUT_DIR, "26047")
    with pytest.raises(ValueError, match="was issued by Moneypenny as 26047"):
        generator.sync_to_gdrive("26047", "TEST", docx_path=docx)
    assert files.events == []


def test_invoice_gdrive_sync_uploads_a_generator_invoice_moneypenny_imported(
    tmp_path, monkeypatch, generator, moneypenny_pre_engine
):
    """A stocktake import of the generator's own invoice does not block its re-sync."""
    moneypenny_pre_engine[2026] = ["26040"]
    files = _real_drive(monkeypatch, tmp_path, "260911 GTA Interos Inc. 26040")
    docx = _invoice_files(generator.OUTPUT_DIR, "26040")
    assert generator.sync_to_gdrive("26040", "TEST", docx_path=docx).endswith("/F1")
    assert ("upload", "SGEPT-invoice26040.pdf") in files.events


def test_upload_refuses_when_moneypenny_cannot_be_read(tmp_path, monkeypatch, moneypenny_report):
    """upload_invoice_files, which register_invoice uses, refuses rather than risk a held number."""

    def unreadable(year):
        raise RuntimeError("Cannot read Moneypenny's invoice counter: connection refused")

    monkeypatch.setattr(moneypenny_report, "series", unreadable)
    gdrive = load_script("gdrive_upload_unreadable", "gdrive_upload.py")
    monkeypatch.setattr(gdrive, "SERVICE_ACCOUNT_PATH", tmp_path)  # any existing path
    files = FakeFiles("unused")
    _install_fake_google(monkeypatch, files)
    with pytest.raises(ValueError, match="cannot be checked against Moneypenny's drafts"):
        gdrive.upload_invoice_files("26047", "TEST", False, [_invoice_files(tmp_path, "26047")])
    assert files.events == []
