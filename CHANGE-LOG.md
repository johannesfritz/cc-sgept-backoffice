# Change log

## 2026-10-27: Every Drive upload reads Moneypenny first, with the CEO's token (JF-4429)

- New `scripts/moneypenny_numbers.py` reads Moneypenny's back-office series report for the generator and for `gdrive_upload.py`. It uses `MNP_API_TOKEN_CEO` and falls back to `MNP_API_TOKEN`. Metis holds `MNP_API_URL`, `MNP_API_TOKEN_CEO` and `MNP_API_TOKEN_LINA`, but no `MNP_API_TOKEN`. The generator issues for the CEO.
- `scripts/gdrive_upload.py`: `_sync_api` and `upload_invoice_files` check Moneypenny immediately before touching Drive. They raise `ValueError`, uploading nothing, for a number a Lina draft holds, a number Moneypenny issued or cancelled, or any number while Moneypenny cannot be read. Its command line, which the handler's STEP F runs, prints `Refused: …` and exits 1. This covers STEP F, `/invoice-gdrive-sync` and filing alike.
- The handler always generates with `--no-sync` and uploads at STEP F, which can be hours later. Before this change nothing checked in between. Now the remaining window is the seconds between the check and the upload.
- `number_in_use` and the upload check also refuse numbers Moneypenny issued. A Lina draft approved before STEP F has left `reserved`, so the upload check needs `issued`. The stocktake recorded 152 of the generator's own invoices in Moneypenny as documents, 26001 to 26038 among them, and imported 2026's with `historical` false. Moneypenny's series report therefore lists `pre_engine`: numbers only historical imports hold, and back-office numbers at or below 26038, which the engine never issues (moneypenny#110). Those numbers stay free, issued or cancelled, so the generator still regenerates and re-syncs them. The reader requires `pre_engine` and refuses without it, so deploy moneypenny#110 first. A generator invoice above 26038 that someone later records in Moneypenny by hand would be refused on re-sync, with Moneypenny's number in the reason.
- `prompts/invoice-handler.md` STEP F: on `Refused`, nothing is committed and the JFM stays at `cos:awaiting-approval`. If Moneypenny cannot be read, the folder is kept and filing waits. If Moneypenny holds the number, the handler's invoice yields, because the draft the CEO saw was internal. The handler renumbers it and writes the new number into the JFM spec and the manifest. `commands/invoice-nipo.md` and `commands/invoice-gdrive-sync.md` state the refusal.
- `scripts/gdrive_upload.py`'s command line moved into `_cli()`, as in the generator, so tests can run it.
- Tests: `tests/test_sync_api.py` covers the STEP F command line refusing a held number, `/invoice-gdrive-sync` through the generator refusing an issued number and uploading an imported one, and `upload_invoice_files` refusing when Moneypenny cannot be read. With the check switched off, the three refusal tests fail because the upload reaches the fake Drive. `tests/test_invoice_numbering.py` covers the CEO token and its fallback, an issued number in use, and an imported number free. The fake series report is now one `moneypenny_report` fixture. 44 tests pass (37 before).

## 2026-10-27: `--next-number` and `number_in_use` also read Moneypenny (JF-4429)

- `scripts/generate-invoice.py`: Moneypenny now reserves an invoice's number when Lina drafts it, before any folder exists. `next_invoice_number` therefore takes the maximum of the local folder, the Drive folder and Moneypenny's back-office counter (`GET /v1/documents/series/`, `last_number`). `number_in_use`, which filing and a number the CEO names both pass through, also refuses a number an open Lina draft holds (the report's `reserved`) or a cancelled draft's void number (`cancelled`), both compared by sequence, and refuses when Moneypenny cannot be read. This is a stopgap until the generator is retired (JF-4217, #1).
- One window remains. With `--no-sync`, or between the check and the Drive upload, Moneypenny does not see the generator's folder, so a Lina draft made then can take the same number. Moneypenny reads Drive at each draft, so a folder that reached Drive is seen.
- Without `MNP_API_URL` and `MNP_API_TOKEN`, or when Moneypenny cannot be read, `--next-number` prints `Refused: …` on stderr and exits 1 instead of giving a number a draft may hold. `--ledger` is unchanged.
- `rules/invoice-governance.md`, `prompts/invoice-handler.md`, `commands/invoice.md` and `commands/invoice-nipo.md` name Moneypenny's counter and say: on `Refused`, stop and report; pick no number another way.
- Tests: `tests/test_invoice_numbering.py` covers the maximum, the series-report read, the refusals (no settings, unreachable, cut-off body, no counter), a number a draft holds, a cancelled draft's number, and filing refused when Moneypenny cannot be read; the shared `generator` fixture fakes the series report. 37 tests pass (28 before).

## 2026-10-27: Count account-suffixed invoice folders in the ledger (JF-4340)

- `scripts/generate-invoice.py`: `_number_of` reads the five-digit sequence from folders ending in `YYNNN` or `YYNNN-NNNNNN`. Ledger rows, number reports and `--next-number` include both forms; full folder names remain in the ledger. One-digit reissue markers stay unparsed.
- The unchanged `number_in_use` now treats a sequence held by a suffixed local or Drive folder as used. The old generator still issues five-digit numbers only.
- `rules/invoice-governance.md`, `knowledge/invoice-spec-schema.md`: distinguish the old generator's five-digit form from Moneypenny's account-suffixed form from switch-on, sharing one yearly sequence.
- `tests/test_invoice_numbering.py`: cover suffix validation, local and fake Drive grouping, reports, next-number stdout, ledger CSV content and used-number detection. No changes to issuance, Drive upload, the retired commands or the handler prompt.
- Verification: 28 tests pass; the plan's sequence-grouping and wording checks and the unchanged Drive folder-naming guard pass. Drive access is faked throughout.
- Follow-up: none within this card; the Monday check and generator retirement remain with their existing cards.

## 2026-10-25: the office inbox routine proposes cards through the capture queue (JCC-8403)

- `prompts/office-inbox-routine.md`: the routine no longer creates JF cards with `linear-api.py` and the `source: office-email` labels. It proposes one card per request through jf-metis `cos-capture-queue.py add`, with `mailbox: office`, `thread_id:` and `request_key:`. The evening flush checks for Johannes's reply and opens an unlabelled Triage card.
- Receipts, invoices for the record, activity reports, weekly summaries and sign-in notices get no card. They are listed under `no_card` in the RESULT block with a reason.
- Spam trashing, the consultant-invoice skip and the sender-mismatch abort are unchanged.
- Merge together with the jf-metis wrapper change, which allows queue add in place of `linear-api.py`. Either change alone breaks the next run.

## 2026-10-21: NIPO academic library invoices carry the requested period (JCC-8834)

- `scripts/generate-invoice.py`: the body period replacement falls back to a substring replace inside a run, and raises if neither finds the template text. The academic library template holds "January 2026 to December 2026" inside one longer run, so the span replacement missed it silently and draft 26040 first showed the template period.
- `tests/test_nipo_period.py`: the regular and academic library tiers both write the requested period. The library case fails without the fix.

## 2026-10-02: Make the manifest pass `claude plugin validate` (plugin-circles)

`plugin.json` no longer declares `agents` as a directory string, which Claude Code rejects, and the repo has no `agents/` folder. Version 0.1.1.

## 2026-10-01: Remove the retired Drive mount stub and its docs (plan invoice-numbering-drive, follow-up)

- `scripts/gdrive_upload.py`: delete the unused `GDRIVE_INVOICING_MAC = None`. `tests/test_drive_sync.py` now patches it with `raising=False`, so the test still proves the Mac sync goes through the API.
- `README.md`, `install.sh`: drop the `SGEPT_GDRIVE_INVOICING` mount override and the stale `INVOICE_OUTPUT_DIR` mention; Drive access is the API on every platform.

## 2026-10-01: Weekly invoice number check on Metis (plan invoice-numbering-drive, stage weekly-check-on-metis)

- No change to `scripts/generate-invoice.py`. Metis (jf-metis commit 6be1505f) now runs `--ledger` every Monday 06:30 UTC under the crontab tag `invoice-number-check` and mails the CEO only when a number is one-sided or newly duplicated, or a pull fails. Both server checkouts are current.
- Passes: `plans/invoice-numbering-drive-passes/weekly-check-on-metis.json`.

## 2026-10-01: Invoice ledger export (plan invoice-numbering-drive, stage invoice-register-export)

- `scripts/generate-invoice.py`: add `invoice_ledger()`, `write_ledger_csv()` and the `--ledger [--year YY] --out PATH` flags. The CSV has one row per number with status `both`, `drive_only`, `local_only` or `duplicate`.

## 2026-10-01: Register invoices made outside the generator (plan invoice-numbering-drive, stage register-outside-invoice)

- `scripts/gdrive_upload.py`: add `upload_invoice_files()`; `_open_drive()` and `_reuse_or_create_folder()` are extracted from `_sync_api` and shared.
- `scripts/generate-invoice.py`: add `register_invoice()` and the `--register --number --client --date --file [--nipo] [--no-sync]` flags.
- `rules/invoice-governance.md`: new section telling people to file hand-made and Metis invoices with `--register` on the day they are sent.

## 2026-10-01: Generators refuse numbers used elsewhere (plan invoice-numbering-drive, stage refuse-used-numbers)

- `scripts/generate-invoice.py`: add `number_in_use()`; the NIPO and standard generators (and so `generate_from_spec`) raise `ValueError` before writing when another local folder or a Drive-only folder holds the number. Regenerating into the same target folder stays allowed.

## 2026-10-01: Next invoice number from Drive and local (plan invoice-numbering-drive, stage next-number-from-drive)

- `scripts/gdrive_upload.py`: add `list_invoice_folders()` (read-only, all pages).
- `scripts/generate-invoice.py`: add `next_invoice_number()`, `invoice_number_report()` and the `--next-number [--year YY]` flag.
- `rules/invoice-governance.md`, `commands/invoice.md`, `commands/invoice-nipo.md`, `prompts/invoice-handler.md`: take the number from `--next-number`; the old "maximum of trailing numbers" sentence is removed.

## 2026-10-01: Mac invoice sync uploads through the Drive API (plan invoice-numbering-drive, stage mac-sync-via-drive-api)

- `scripts/gdrive_upload.py`: `sync_to_gdrive` uses one backend, `_sync_api`, on every platform. `_sync_macos`, the mount-path constants and the platform dispatch are removed. `GDRIVE_INVOICING_MAC` stays as an unused `None` because `tests/test_drive_sync.py` patches it.
- `scripts/generate-invoice.py`: the Drive for desktop path constants are removed.
- `tests/test_sync_api.py`: unit test for folder reuse and file replacement against a fake Drive service.
- `commands/invoice.md`, `commands/invoice-nipo.md`, `commands/invoice-gdrive-sync.md`, `rules/invoice-governance.md`: describe the API upload.
- `rules/invoice-governance.md`: wording follow-up so no sync doc names the Drive for desktop folder.
