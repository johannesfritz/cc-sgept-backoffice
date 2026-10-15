---
paths:
  - sgept-backoffice/invoicing/**
  - sgept-backoffice/templates/invoices/**
  - .claude/commands/invoice*.md
  - .claude/scripts/generate-invoice.py
---

# Invoice Governance

Invariants every invoice must satisfy. Violations have produced broken invoices in prior runs — each rule here earns its place.

## Numbering

- **Old generator numbers: 5 digits, no separator.** The old generator issued only `YYNNN`, such as `26015` or `26007`. Never `26-015`, `26/015` or `26_015`. Strip any separators before passing a number to the script.
- **Moneypenny numbers: `YYNNN-NNNNNN`.** The five-digit sequence, a hyphen, then exactly six digits for the revenue account: `26043-410210`. Preserve the account suffix.
- **One yearly sequence across both forms.** The suffix does not create a separate series. The ledger's `number` column holds the sequence; its `drive_folders` column preserves the full folder names, including account suffixes.
- **Moneypenny issues every new number.** Draft new invoices with `/invoice` or `/invoice-nipo` in the Business Development plugin, or ask Lina; Moneypenny numbers each one when its drafter approves it. `generate-invoice.py --next-number` refuses. Never pick a number by hand or by listing a folder.

## Dates

- **Invoice date is the actual send date** unless the requester explicitly says otherwise.
- **Due date is always 30 days after invoice date.** Computed by the script; never manually overridden.

## Subscription period (NIPO only)

- Format: `"Month YYYY - Month YYYY"` with space-hyphen-space separator.
- Both sides use full `"Month YYYY"`. Never just the month — the body text reads literally "the NIPO dataset for {period_start} will be delivered ... up until and including the {period_end} deliverable", so the year must appear on both sides to avoid ambiguity.
- `period_end` is the LAST month of delivery, not the following month.

## Amounts

- Two-decimal fixed-point with comma thousands separator: `7,000.00`, `24,050.00`.
- Currency code explicit in every invoice: `CHF`, `EUR`, or `USD`.

## Bank account

- Selected automatically from the `currency` field:
  - CHF → `CH80 0078 1624 8968 1200 0`
  - EUR → `CH53 0078 1624 8968 1200 1`
  - USD → `CH26 0078 1624 8968 1200 2`
- Bank: St.Galler Kantonalbank AG, BIC `KBSGCH22`.

## Verification (MANDATORY for NIPO, recommended for standard)

After generation, read the `.docx` back and confirm every field matches the input:

- [ ] Invoice number matches (no template remnant `26003`/`26005`/`25031`).
- [ ] `St.Gallen, DD Month YYYY` header date matches the invoice date.
- [ ] Invoice date line `DD Mon YYYY` matches.
- [ ] Due date is exactly 30 days after invoice date.
- [ ] Salutation uses correct name (first name for regular tier; full form "Mr X" for academic).
- [ ] Body `period_start` and `period_end` correct with NO duplicated year (never "May 2026 2026").
- [ ] Currency code matches (`USD` not `CHF` when USD requested).
- [ ] Amount matches the value passed.
- [ ] IBAN matches the currency selected.

If any check fails: stop, report the paragraph number + mismatch to the requester, do NOT claim the invoice is ready.

## Overwrite semantics (Drive sync)

The sync uploads through the Drive API on every platform. It never reads or writes a locally synced copy of the Drive, which can list a stale subset of the invoice folders.

- A Drive folder whose name ends in ` {NUMBER}` is reused if present (any date prefix, any type).
- `SGEPT-invoice{NUMBER}.docx` and `.pdf` inside are deleted before the fresh files are uploaded.
- No `(1)` suffixes. No stale duplicates.

## Invoices made outside the generator

An invoice written by hand, or drafted by Metis, still needs its number filed. On the day it is sent, run:

`python3 scripts/generate-invoice.py --register --number NNNNN --client "Client Name" --date YYYY-MM-DD --file path/to/invoice.pdf [--file ...] [--nipo]`

`--register` refuses a number already used locally or on Drive. Otherwise it creates the local folder, copies the files in and uploads them to the matching Drive folder. Add `--no-sync` to skip the upload.

## VAT (standard invoices)

- Default: `"No VAT is applied."`
- EU recipient (any of: Austria, Belgium, Bulgaria, Croatia, Cyprus, Czech Republic, Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, Netherlands, Poland, Portugal, Romania, Slovakia, Slovenia, Spain, Sweden): append `" The reverse charge mechanism applies."`
- Other jurisdictions (e.g. Australia GST): use the specific wording the requester provides.
