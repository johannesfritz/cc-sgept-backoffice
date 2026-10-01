# Change log

## 2026-10-01: Next invoice number from Drive and local (plan invoice-numbering-drive, stage next-number-from-drive)

- `scripts/gdrive_upload.py`: add `list_invoice_folders()` (read-only, all pages).
- `scripts/generate-invoice.py`: add `next_invoice_number()`, `invoice_number_report()` and the `--next-number [--year YY]` flag.
- `rules/invoice-governance.md`, `commands/invoice.md`, `commands/invoice-nipo.md`, `prompts/invoice-handler.md`: take the number from `--next-number`; the old "maximum of trailing numbers" sentence is removed.
