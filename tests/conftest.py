"""Shared fixtures for the invoicing acceptance tests.

The generator and the Drive module are loaded from scripts/ by file path,
because generate-invoice.py is not an importable module name. Drive access is
replaced by a fake ``gdrive_upload`` module placed in ``sys.modules``: the
generator must import ``gdrive_upload`` at call time so the fake is the one it
sees.
"""
import importlib.util
import sys
import types
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load_script(module_name: str, filename: str) -> types.ModuleType:
    """Load a module from scripts/ by file name, with scripts/ on sys.path."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeDrive:
    """Stands in for the Drive invoicing folder."""

    def __init__(self) -> None:
        self.folders: list[str] = []
        self.uploads: list[tuple[str, list[str]]] = []

    def module(self) -> types.ModuleType:
        """Return a ``gdrive_upload`` stand-in backed by this fake folder."""
        fake = types.ModuleType("gdrive_upload")
        fake.list_invoice_folders = lambda: list(self.folders)

        def upload_invoice_files(inv_num: str, abbrev: str, is_nipo: bool, paths: list) -> str:
            self.uploads.append((inv_num, sorted(Path(p).name for p in paths)))
            return f"https://drive.google.com/drive/folders/fake-{inv_num}"

        def sync_to_gdrive(*args, **kwargs):
            raise AssertionError("the Drive sync must not run in these tests")

        fake.upload_invoice_files = upload_invoice_files
        fake.sync_to_gdrive = sync_to_gdrive
        return fake


@pytest.fixture
def drive(monkeypatch: pytest.MonkeyPatch) -> FakeDrive:
    """Replace the Drive module with an empty fake Drive folder."""
    fake = FakeDrive()
    monkeypatch.setitem(sys.modules, "gdrive_upload", fake.module())
    return fake


@pytest.fixture
def generator(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drive: FakeDrive) -> types.ModuleType:
    """The invoice generator, writing into an empty temporary invoicing folder."""
    gen = load_script("generate_invoice", "generate-invoice.py")
    out = tmp_path / "invoicing"
    out.mkdir()
    monkeypatch.setattr(gen, "OUTPUT_DIR", out)
    return gen


NIPO_SPEC = {
    "type": "nipo",
    "invoice_date": "2026-10-01",
    "currency": "CHF",
    "amount": 500,
    "tier": "academic_student",
    "subscription_period": "October 2026 - September 2027",
    "abbrev": "TEST",
    "sync": False,
    "recipient": {
        "company": "Test University",
        "name": "Jane Doe",
        "street": "1 Test Street",
        "city": "1000 Testville",
        "country": "Testland",
    },
}


def nipo_spec(number: str) -> dict:
    """A NIPO academic invoice spec for Test University under ``number``, without Drive sync."""
    return dict(NIPO_SPEC, invoice_number=number)
