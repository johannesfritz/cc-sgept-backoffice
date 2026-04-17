---
description: Re-sync an invoice to the Google Drive folder (regenerates PDF, overwrites)
---

Re-sync an existing invoice to the Google Drive shipping folder. Use this after editing a generated `.docx` in Word when you want the Drive folder to reflect the latest version.

The command:
1. Finds the local `.docx` (searches `sgept-backoffice/invoicing/` recursively)
2. Regenerates the `.pdf` via Word (`docx2pdf`)
3. Copies both files to the Drive folder as `SGEPT-invoice[NUMBER].docx` / `.pdf`
4. Overwrites any existing `SGEPT-invoice[NUMBER].*` files in that folder — no version conflicts

Note: `/invoice` and `/invoice-nipo` already sync to Drive automatically on first generation. This command is only for re-syncs.

## Required Information

Collect via AskUserQuestion:

1. **Invoice Number** — 5 digits (e.g., `26007`)
2. **Abbreviation** — only needed if no Drive folder ending in ` [NUMBER]` already exists (a new folder will be created named `YYMMDD [NIPO ][ABBREV] [NUMBER]`). If the folder exists, the script reuses it and abbrev can be a placeholder.
3. **Is NIPO?** — only matters if a new folder will be created (to prefix `NIPO` into the folder name)

## Process

```bash
cd /Users/johannesfritz/Documents/GitHub/jf-private/jf-ceo/sgept-backoffice/scripts
python3 << 'PYEOF'
import importlib.util
spec = importlib.util.spec_from_file_location('gi', 'generate-invoice.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

dest = mod.sync_to_gdrive(
    invoice_number='INVOICE_NUMBER',
    abbrev='ABBREV',
    is_nipo=IS_NIPO,  # True or False
)
print(f'Synced to: {dest}')
PYEOF
```

## Overwrite Semantics

- If a Drive folder whose name ends in ` [NUMBER]` exists (any date prefix, any type), it is reused.
- `SGEPT-invoice[NUMBER].docx` and `SGEPT-invoice[NUMBER].pdf` inside that folder are removed before the fresh copies are placed.
- No `(1)` suffixes, no stale duplicates.

## Output

Destination: `.../SGEPT admin/dbx/SGEPT/0 admin/5 invoicing/YYMMDD [NIPO ][ABBREV] [NUMBER]/`

Contains `SGEPT-invoice[NUMBER].docx` and `SGEPT-invoice[NUMBER].pdf`.
