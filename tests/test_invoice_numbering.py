"""Acceptance tests for invoice numbering (plan invoice-numbering-drive).

The next number and every refusal must take the Drive invoicing folder and
the local invoicing folder into account, because invoices made outside the
generator exist on one side only.
"""
import csv
import http.client
import io
import json
import sys
import urllib.error

import pytest

from conftest import load_script, nipo_spec


def _require(gen, name):
    func = getattr(gen, name, None)
    assert callable(func), f"generate-invoice.py has no {name}()"
    return func


def _local(gen, *names):
    for name in names:
        (gen.OUTPUT_DIR / name).mkdir()


# next-number-from-drive

def test_next_number_takes_max_of_drive_and_local(generator, drive):
    _local(generator, "260101 NIPO A 26010", "260102 B 26012")
    drive.folders = ["260101 NIPO A 26010", "260103 C 26014", "251201 D 25042", "templates"]
    assert _require(generator, "next_invoice_number")(year=26) == "26015"


def test_next_number_starts_new_year_at_001(generator, drive):
    _local(generator, "261201 A 26040")
    drive.folders = ["261201 A 26040"]
    assert _require(generator, "next_invoice_number")(year=27) == "27001"


def test_report_lists_one_sided_and_duplicate_numbers(generator, drive):
    _local(generator, "260101 A 26010", "260102 B 26012", "260413 C 26015", "260417 D 26015")
    drive.folders = ["260101 A 26010", "260103 E 26014", "260413 C 26015"]
    report = _require(generator, "invoice_number_report")(year=26)
    assert report["drive_only"] == ["26014"]
    assert report["local_only"] == ["26012"]
    assert sorted(report["duplicates"]["26015"]) == ["260413 C 26015", "260417 D 26015"]


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
    local, remote, year = generator._numbers_by_side(26)
    assert year == "26"
    assert local == {
        "26043": ["261021 NIPO Acme 26043-410210"],
        "26044": ["261022 C 26044-410200"],
    }
    assert remote == {
        "26010": ["260101 B 26010"],
        "26043": ["261021 NIPO Acme 26043-410200"],
    }
    assert generator.next_invoice_number(26) == "26045"


def test_next_number_cli_counts_suffixed_drive_folder(generator, drive, monkeypatch, capsys):
    drive.folders = ["261021 NIPO Acme 26043-410200", "260101 B 26010"]
    monkeypatch.setattr(sys, "argv", ["generate-invoice.py", "--next-number", "--year", "26"])
    generator._cli()
    captured = capsys.readouterr()
    assert captured.out == "26044\n"
    assert "Drive only (no local copy): 26010, 26043" in captured.err


def test_ledger_cli_keeps_sequences_and_full_suffixed_folder_names(generator, drive, tmp_path, monkeypatch):
    _local(generator, "261021 NIPO Acme 26043-410210", "261022 C 26044-410200")
    drive.folders = [
        "261021 NIPO Acme 26043-410200", "260101 B 26010",
        "261022 C 26044", "261023 D 26044-410210",
    ]
    report = generator.invoice_number_report(26)
    assert report == {
        "drive_only": ["26010"], "local_only": [],
        "duplicates": {"26044": ["261022 C 26044", "261023 D 26044-410210"]},
    }
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


# moneypenny-counter (JF-4429)

def test_next_number_takes_moneypenny_counter_when_higher(generator, drive, moneypenny):
    """A number Lina's draft reserved is in Moneypenny's counter before any folder exists."""
    drive.folders = ["261021 NIPO Acme 26043-410200"]
    moneypenny[2026] = 26046
    assert generator.next_invoice_number(26) == "26047"
    moneypenny[2026] = 26040
    assert generator.next_invoice_number(26) == "26044"


def test_moneypenny_counter_is_read_from_the_series_report(monkeypatch):
    """The counter and the drafts' numbers come from the series report for the year, with the service token."""
    gen = load_script("generate_invoice_reader", "generate-invoice.py")
    seen = []

    def urlopen(request, timeout):
        seen.append((request.full_url, request.get_header("Authorization"), timeout))
        body = {"series": "backoffice", "year": 2026, "last_number": 26046, "reserved": ["26046-410210"]}
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setenv("MNP_API_URL", "https://mnp.example.invalid/")
    monkeypatch.setenv("MNP_API_TOKEN", "fixture-token")
    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    assert gen.moneypenny_series(2026) == {"last_number": 26046, "reserved": ["26046-410210"], "cancelled": []}
    assert seen == [("https://mnp.example.invalid/v1/documents/series/?series=backoffice&year=2026",
                     "Bearer fixture-token", 20)]


def test_next_number_cli_refuses_without_moneypenny(drive, tmp_path, monkeypatch, capsys):
    """Without Moneypenny's counter no number is printed, since a draft may hold the next one."""
    gen = load_script("generate_invoice_refusal", "generate-invoice.py")
    monkeypatch.setattr(gen, "OUTPUT_DIR", tmp_path)
    monkeypatch.delenv("MNP_API_URL", raising=False)
    monkeypatch.setenv("MNP_API_TOKEN", "fixture-token")
    monkeypatch.setattr(sys, "argv", ["generate-invoice.py", "--next-number", "--year", "26"])
    with pytest.raises(SystemExit) as exit_info:
        gen._cli()
    assert exit_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Refused: MNP_API_URL and MNP_API_TOKEN must be set" in captured.err


@pytest.mark.parametrize(
    "urlopen_effect",
    [urllib.error.URLError("connection refused"), http.client.IncompleteRead(b"{"), {"series": "backoffice"}],
    ids=["unreachable", "cut_off", "no_last_number"],
)
def test_next_number_cli_refuses_when_moneypenny_cannot_be_read(drive, tmp_path, monkeypatch, capsys, urlopen_effect):
    """An unreachable service, a cut-off body or a report without the counter prints no number."""
    gen = load_script("generate_invoice_unreadable", "generate-invoice.py")
    monkeypatch.setattr(gen, "OUTPUT_DIR", tmp_path)
    monkeypatch.setenv("MNP_API_URL", "https://mnp.example.invalid")
    monkeypatch.setenv("MNP_API_TOKEN", "fixture-token")

    def urlopen(request, timeout):
        if isinstance(urlopen_effect, Exception):
            raise urlopen_effect
        return io.BytesIO(json.dumps(urlopen_effect).encode())

    monkeypatch.setattr("urllib.request.urlopen", urlopen)
    monkeypatch.setattr(sys, "argv", ["generate-invoice.py", "--next-number", "--year", "26"])
    with pytest.raises(SystemExit) as exit_info:
        gen._cli()
    assert exit_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "Refused: Cannot read Moneypenny's invoice counter" in captured.err


def test_number_held_by_a_lina_draft_is_in_use(generator, moneypenny_reserved):
    """A number Johannes names himself is refused while a Lina draft holds it, suffixed or not."""
    moneypenny_reserved[2026] = ["26047-410210", "26049"]
    assert "held by a Lina draft in Moneypenny as 26047-410210" in generator.number_in_use("26047")
    assert "as 26049" in generator.number_in_use("26049")
    assert generator.number_in_use("26048") is None


def test_number_of_a_cancelled_lina_draft_is_in_use(generator, moneypenny_cancelled):
    """A rejected draft below the counter's top stays void in Moneypenny and never reaches Drive."""
    moneypenny_cancelled[2026] = ["26045-410210"]
    assert "cancelled Lina draft that Moneypenny keeps as 26045-410210" in generator.number_in_use("26045")
    assert generator.number_in_use("26046") is None


def test_number_counts_as_in_use_when_moneypenny_cannot_be_read(generator, monkeypatch):
    """Filing refuses rather than risk a number a Lina draft may hold."""

    def unreadable(year):
        raise RuntimeError("MNP_API_URL and MNP_API_TOKEN must be set to read Moneypenny's invoice counter")

    monkeypatch.setattr(generator, "moneypenny_series", unreadable)
    assert "cannot be checked against Moneypenny's drafts" in generator.number_in_use("26048")
    with pytest.raises(ValueError, match="cannot be checked against Moneypenny's drafts"):
        generator.generate_from_spec(nipo_spec("26048"))
