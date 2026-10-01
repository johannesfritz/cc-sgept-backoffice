"""Unit test for gdrive_upload._sync_api against a fake Drive service (no network)."""
import sys
import types
from pathlib import Path

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


def test_sync_api_reuses_folder_and_replaces_files(tmp_path: Path, monkeypatch) -> None:
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
