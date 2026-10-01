# Change log

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
