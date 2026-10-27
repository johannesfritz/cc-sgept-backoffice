"""Acceptance tests for invoice numbering (plan invoice-numbering-drive).

Every refusal must take the Drive invoicing folder and the local invoicing
folder into account, because invoices made outside the generator exist on one
side only. Moneypenny now issues new numbers, so --next-number refuses
(client-documents plan, cutover-checks).
"""
import csv
import subprocess
import sys

import pytest

from conftest import SCRIPTS, nipo_spec


def _require(gen, name):
    func = getattr(gen, name, None)
    assert callable(func), f"generate-invoice.py has no {name}()"
    return func


def _local(gen, *names):
    for name in names:
        (gen.OUTPUT_DIR / name).mkdir()


# next-number-refuses

def test_next_number_refuses_and_names_the_plugin():
    done = subprocess.run([sys.executable, str(SCRIPTS / "generate-invoice.py"), "--next-number"],
                          capture_output=True, text=True, timeout=60)
    assert done.returncode == 1
    assert done.stdout == ""
    assert "Moneypenny issues invoice numbers" in done.stderr
    assert "/invoice-nipo in the Business Development plugin" in done.stderr


# refuse-used-numbers

def test_refuses_number_used_by_another_local_folder(generator, drive):
    _local(generator, "260101 NIPO Other Client 26014")
    with pytest.raises(ValueError, match="26014"):
        generator.generate_from_spec(nipo_spec("26014"))
    assert sorted(p.name for p in generator.OUTPUT_DIR.iterdir()) == ["260101 NIPO Other Client 26014"]


def test_refuses_number_present_only_on_drive(generator, drive):
    drive.folders = ["260101 SGEPT - IMF 26016"]
    with pytest.raises(ValueError, match="26016"):
        generator.generate_from_spec(nipo_spec("26016"))
    assert list(generator.OUTPUT_DIR.iterdir()) == []


def test_regenerating_same_invoice_is_allowed(generator, drive):
    _local(generator, "261001 NIPO Test University 26017")
    drive.folders = ["261001 NIPO TEST 26017"]
    out = generator.generate_from_spec(nipo_spec("26017"))
    assert out.parent.name == "261001 NIPO Test University 26017"


# register-outside-invoice

def test_register_files_invoice_locally_and_uploads(generator, drive, tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    pdf = source / "MSF Förderung 2026 26040.pdf"
    pdf.write_bytes(b"%PDF-1.4 hand-made")
    register = _require(generator, "register_invoice")
    folder = register(number="26040", client="Max Schmidheiny Stiftung",
                      invoice_date="2026-08-15", files=[pdf])
    assert folder == generator.OUTPUT_DIR / "260815 Max Schmidheiny Stiftung 26040"
    assert (folder / pdf.name).read_bytes() == b"%PDF-1.4 hand-made"
    assert drive.uploads == [("26040", [pdf.name])]


def test_register_refuses_used_number(generator, drive, tmp_path):
    _local(generator, "260101 NIPO Other Client 26014")
    pdf = tmp_path / "hand-made 26014.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    register = _require(generator, "register_invoice")
    with pytest.raises(ValueError, match="26014"):
        register(number="26014", client="Someone", invoice_date="2026-10-01", files=[pdf])
    assert drive.uploads == []


# invoice-register-export

def test_ledger_classifies_numbers(generator, drive):
    _local(generator, "260101 A 26001", "260102 B 26002", "260413 C 26003", "260417 D 26003")
    drive.folders = ["260101 A 26001", "260103 E 26004", "251201 F 25042", "templates"]
    rows = _require(generator, "invoice_ledger")(year=26)
    assert [(r["number"], r["status"]) for r in rows] == [
        ("26001", "both"), ("26002", "local_only"), ("26003", "duplicate"), ("26004", "drive_only"),
    ]


# ledger-suffix (JF-4340)

@pytest.mark.parametrize("folder_name, expected", [
    ("260101 B 26010", "26010"),
    ("261021 NIPO Acme 26043-410200", "26043"),
    ("261021 NIPO Acme 26043-410210", "26043"),
    ("260907 Teneo 26015-2", None),
    ("261021 Acme 26043-41021", None),
    ("261021 Acme 26043-4102100", None),
    ("261021 Acme 26043-41021A", None),
    ("261021 Acme 26043-", None),
    ("261021 Acme 126043-410210", None),
    ("261021 Acme 26043-410210 extra", None),
])
def test_folder_number_reads_sequence_with_optional_six_digit_suffix(generator, folder_name, expected):
    assert generator._number_of(folder_name) == expected


def test_suffixed_folders_group_by_sequence_on_both_sides(generator, drive):
    _local(generator, "261021 NIPO Acme 26043-410210", "261022 C 26044-410200")
    drive.folders = [
        "261021 NIPO Acme 26043-410200", "260101 B 26010",
        "251201 D 25042-410210", "260907 Teneo 26015-2",
    ]
    local, remote = generator._numbers_by_side(26)
    assert local == {
        "26043": ["261021 NIPO Acme 26043-410210"],
        "26044": ["261022 C 26044-410200"],
    }
    assert remote == {
        "26010": ["260101 B 26010"],
        "26043": ["261021 NIPO Acme 26043-410200"],
    }


def test_ledger_cli_keeps_sequences_and_full_suffixed_folder_names(generator, drive, tmp_path, monkeypatch):
    _local(generator, "261021 NIPO Acme 26043-410210", "261022 C 26044-410200")
    drive.folders = [
        "261021 NIPO Acme 26043-410200", "260101 B 26010",
        "261022 C 26044", "261023 D 26044-410210",
    ]
    ledger_path = tmp_path / "ledger.csv"
    monkeypatch.setattr(sys, "argv", [
        "generate-invoice.py", "--ledger", "--year", "26", "--out", str(ledger_path),
    ])
    generator._cli()
    with ledger_path.open(newline="") as ledger_file:
        rows = list(csv.DictReader(ledger_file))
    assert rows == [
        {"number": "26010", "status": "drive_only", "local_folders": "",
         "drive_folders": "260101 B 26010"},
        {"number": "26043", "status": "both",
         "local_folders": "261021 NIPO Acme 26043-410210",
         "drive_folders": "261021 NIPO Acme 26043-410200"},
        {"number": "26044", "status": "duplicate",
         "local_folders": "261022 C 26044-410200",
         "drive_folders": "261022 C 26044 | 261023 D 26044-410210"},
    ]


@pytest.mark.parametrize("side", ["local", "drive"])
def test_five_digit_number_is_in_use_when_suffixed_folder_exists(generator, drive, side):
    folder_name = "261021 NIPO Acme 26043-410210"
    if side == "local":
        _local(generator, folder_name)
    else:
        drive.folders = [folder_name]
    reason = generator.number_in_use("26043")
    assert reason is not None and folder_name in reason
    assert generator.number_in_use("26044") is None
