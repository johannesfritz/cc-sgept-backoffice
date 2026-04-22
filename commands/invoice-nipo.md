---
description: Generate a NIPO subscription invoice (regular, academic library, or academic)
---

Generate a NIPO (New Industrial Policy Observatory) subscription invoice.

## Invariants (MUST follow — bugs caught in prior runs)

These rules are MANDATORY. Prior runs produced broken invoices when any were violated.

1. **Invoice numbers have NO hyphen.** The format is a single 5-digit string: `26015`, `26007`, `26001`. Never `26-015`, `26-0015`, `26/015`. If the user types any separator, normalize to the raw 5 digits before passing to the script.
2. **`subscription_period` argument uses " - " as separator** (space-hyphen-space): `"May 2026 - April 2027"`. Use full `"Month YYYY"` on both sides — never just the month. The body text reads literally "...the NIPO dataset for {period_start} will be delivered ... up until and including the {period_end} deliverable" so period_start MUST be the first month of the subscription and period_end MUST be the last.
3. **Invoice date is the actual date you are sending the invoice**, not a future or backdated value unless the user explicitly says so. Default to today.
4. **After generation, run the verification step (below).** The script cannot always detect if a template has been edited; verification catches regressions the script cannot.

## NIPO Tiers

| Tier | Default Amount | Payment Options |
|------|---------------|-----------------|
| **Regular** | CHF 7,000 | Bank transfer only |
| **Academic Library** | CHF 1,250 | Bank transfer + Stripe |
| **Academic/Student** | CHF 500 | Bank transfer + Stripe |

## Required Information

Collect the following from the user using AskUserQuestion (only for what you cannot infer from their request):

1. **Invoice Number** — 5 digits, no hyphen (e.g., `26015`)
2. **Invoice Date** — default to today; confirm with user if unclear
3. **NIPO Tier** — regular, academic_library, or academic_student
4. **Currency** — CHF, EUR, or USD
5. **Amount** — default to tier default; user may override
6. **Recipient Details:**
   - Institution/Organization name
   - Contact person name (full name)
   - Street address
   - City/postal code
   - Country
7. **Subscription Period** — format `"Month YYYY - Month YYYY"` (e.g., `"May 2026 - April 2027"`)
8. **Abbreviation** — short identifier for the Drive folder name (e.g. `IADB`, `TENEO`). Ask the user — do NOT auto-derive.

## Generation Process

After collecting all information, normalize the invoice number (strip any hyphens/separators so it is exactly 5 digits), then run:

```bash
cd "$HOME/Documents/GitHub/jf-private/jf-ceo/sgept-backoffice/scripts"
python3 -c "
import importlib.util
spec = importlib.util.spec_from_file_location('gi', 'generate-invoice.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

output = mod.generate_nipo_invoice(
    invoice_number='INVOICE_NUMBER',
    invoice_date='INVOICE_DATE',
    currency='CURRENCY',
    amount=AMOUNT,
    recipient={
        'company': 'INSTITUTION',
        'name': 'CONTACT_NAME',
        'street': 'STREET',
        'city': 'CITY',
        'country': 'COUNTRY'
    },
    tier='TIER',
    subscription_period='PERIOD',
    abbrev='ABBREV',
)
print(f'Invoice saved to: {output}')
"
```

Replace the placeholders with the collected values. `INVOICE_NUMBER` must be 5 digits with no hyphen.

## Verification Step (MANDATORY)

After the script prints `Invoice saved to: ...`, verify the generated .docx by reading back its text content. Run:

```bash
python3 -c "
from docx import Document
doc = Document('FULL_OUTPUT_PATH')
for i, p in enumerate(doc.paragraphs):
    text = p.text.replace('\t', ' | ')
    if text.strip():
        print(f'[{i:2d}] {text}')
"
```

Then check ALL of the following against what you passed in:

- [ ] Invoice number line shows the correct 5-digit number (no template remnant like `26003`, `26005`, `25031`).
- [ ] Right-side header date (`St.Gallen, DD Month YYYY`) matches the invoice date you passed — check month AND year.
- [ ] Invoice date line (`DD Mon YYYY`) matches.
- [ ] Due date line (`DD Mon YYYY`) is exactly 30 days after the invoice date.
- [ ] Salutation uses the correct name.
- [ ] Body paragraph contains the correct `period_start` and `period_end` with NO duplicated year (e.g., never "May 2026 2026").
- [ ] Currency code matches (e.g., `USD` not `CHF` when USD was requested).
- [ ] Amount matches the value passed.
- [ ] IBAN matches the currency selected (CHF/EUR/USD).

If ANY check fails, the script has regressed — stop, report the failure to the user with the paragraph number and the mismatch, and do NOT claim the invoice is ready.

## Output

Two locations (the script handles both automatically):

1. **Local working copy:** `sgept-backoffice/invoicing/YYMMDD NIPO [Institution] [Number]/Invoice-[NUMBER]-[Institution]-NIPO.docx`
2. **Google Drive shipping folder:** `.../SGEPT admin/dbx/SGEPT/0 admin/5 invoicing/YYMMDD NIPO [ABBREV] [Number]/SGEPT-invoice[NUMBER].docx` + `.pdf`

The Drive sync runs automatically after generation: the script converts the `.docx` to PDF via Word (`docx2pdf`), then copies both files to Drive with the standardized `SGEPT-invoice[NUMBER]` naming. If a folder ending in ` [NUMBER]` already exists, the files inside are overwritten — no version drift.

## Re-syncing after edits

If you open the generated `.docx` in Word and edit it, run `/invoice-gdrive-sync [NUMBER]` to regenerate the PDF and overwrite the Drive folder.

## Stripe Payment Links

For academic tiers, the template includes the Stripe payment link:
- **Academic Library**: https://buy.stripe.com/00wdRagmy8rido5gDR1ck0q
- **Academic/Student**: https://buy.stripe.com/dR65ncckG0InaVqaEE

## Bank Account Selection

The script automatically selects the bank account based on currency:
- **CHF**: CH80 0078 1624 8968 1200 0
- **EUR**: CH53 0078 1624 8968 1200 1
- **USD**: CH26 0078 1624 8968 1200 2

## Template Elements

The generated invoice includes:
- SGEPT logo in header
- Recipient address block
- Invoice number, invoice date, due date
- NIPO subscription details (period covered in body text)
- Purchase fee + Invoice total lines
- Bank payment details (IBAN, BIC)
- Stripe link (academic tiers only)
- Signature block

## How the script works (for debugging)

`generate_nipo_invoice` in `scripts/generate-invoice.py` uses python-docx to open the tier's template and apply **run-level edits** to specific paragraphs identified by index (see `NIPO_LAYOUTS` in the script). Each tier has a layout describing paragraph indices plus the expected template text to replace (e.g., `'tpl_inv_num': '26003'` for regular tier). The helper `_replace_span` handles cases where Word has split text across multiple `<w:r>` runs.

**Do not** change template text values in `NIPO_LAYOUTS` without first re-inspecting the template `.docx` — the run structure is template-specific and must match exactly. If a template is edited in Word, run:

```bash
python3 -c "
from docx import Document
doc = Document('templates/invoices/SGEPT - Invoice NIPO regular.docx')
for i, p in enumerate(doc.paragraphs):
    print(f'[{i:2d}] {repr(p.text)}')
    for j, r in enumerate(p.runs):
        print(f'    run[{j}] {repr(r.text)}')
"
```

to re-derive the layout before updating `NIPO_LAYOUTS`.
