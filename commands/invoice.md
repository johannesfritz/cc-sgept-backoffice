---
description: Generate a standard SGEPT professional services invoice
---

Generate a professional services invoice for the St.Gallen Endowment.
For NIPO subscription invoices, redirect the user to `/invoice-nipo` instead.

## Step 1: Collect Information

From the user's message, extract or ask for (via AskUserQuestion):

1. **Invoice Number** — check recent numbers in `sgept-backoffice/invoicing/` and suggest the next sequential one
2. **Invoice Date** — default to today
3. **Currency** (CHF, EUR, or USD)
4. **Recipient**: company, contact person name, street, city, country
5. **Abbreviation** — short identifier for the Drive folder name (e.g. `ERCO`, `IADB`, `GRAINS-AUS`). Ask the user — do NOT auto-derive.
6. **Invoice Type**: "deliverable" (fixed-scope items) or "hours" (time & materials)
7. **Project title** — used as the subject line (e.g., "GTA Policy Intelligence Dashboard — Founding Member Program")
8. **Service description** — what is being invoiced (verbal summary for the intro paragraph)
9. **Line items**:
   - Deliverable type: description + amount per item
   - Hours type: person name + hours + hourly rate per person
10. **Total amount**
11. **Agreement reference** (optional) — specific agreement name and date, if the user provides one

## Step 2: Compose Invoice Content

You MUST compose these text sections before calling the script. Follow these rules exactly:

### Subject Line
The project title as given by the user. Nothing else.
- Example: `"GTA Policy Intelligence Dashboard — Founding Member Program"`
- Example: `"Trade Policy Advisory Services — Phase 2"`

### Intro Paragraph
Compose 1-3 sentences:

**Sentence 1 (agreement + deliverable reference):**
- Default: `"In line with our agreement, we hereby issue an invoice for [what is being invoiced]."`
- If user specifies an agreement: `"In accordance with our [Agreement Name] dated [Date], we hereby issue an invoice for [what]."`

**Sentence 2+ (substance):**
Concise verbal description of what the invoice covers. Draw from the user's description of the services/deliverables. Keep it factual and brief.

### Items List
Build the items list matching the invoice type:

**Deliverable type** — each item has `description` and `amount`:
```python
items=[{"description": "GTA Dashboard — Year 1 Subscription", "amount": 12000}]
items_type="deliverable"
```

**Hours type** — each item has `description`, `hours`, `rate`, `total`:
```python
items=[
    {"description": "Johannes Fritz", "hours": 45, "rate": 300, "total": 13500},
    {"description": "Patrick Buess", "hours": 35, "rate": 250, "total": 8750}
]
items_type="hours"
```

### VAT Note
- **Default** (non-EU): `"No VAT is applied."`
- **EU member states**: `"No VAT is applied. The reverse charge mechanism applies."`
- **Custom**: use whatever the user specifies (e.g., GST clauses)

Determine EU membership from the recipient's country automatically.

## Step 3: Generate the Invoice

```bash
cd "$HOME/Documents/GitHub/jf-private/jf-ceo/sgept-backoffice/scripts"
python3 << 'PYEOF'
import sys; sys.path.insert(0, '.')
import importlib
mod = importlib.import_module('generate-invoice')

output = mod.generate_standard_invoice(
    invoice_number='INVOICE_NUMBER',
    invoice_date='INVOICE_DATE',
    currency='CURRENCY',
    recipient={
        'company': 'COMPANY',
        'name': 'CONTACT_NAME',
        'street': 'STREET',
        'city': 'CITY',
        'country': 'COUNTRY'
    },
    subject_line='SUBJECT_LINE',
    intro_paragraph='INTRO_PARAGRAPH',
    items=[ITEMS_LIST],
    items_type='ITEMS_TYPE',
    total=TOTAL,
    vat_note='VAT_NOTE',
    abbrev='ABBREV',
)
print(f'Invoice saved to: {output}')
PYEOF
```

## Output

Two locations (the script handles both automatically):

1. **Local working copy:** `sgept-backoffice/invoicing/YYMMDD [Descriptor] [Company] [NUMBER]/Invoice-[NUMBER]-[COMPANY].docx`
2. **Google Drive shipping folder:** `.../SGEPT admin/dbx/SGEPT/0 admin/5 invoicing/YYMMDD [ABBREV] [NUMBER]/SGEPT-invoice[NUMBER].docx` + `.pdf`

The Drive sync runs automatically after generation: the script converts the `.docx` to PDF via Word (`docx2pdf`), then copies both files to Drive with the standardized `SGEPT-invoice[NUMBER]` naming. If a folder ending in ` [NUMBER]` already exists, the files inside are overwritten — no version drift.

The script auto-selects the bank account by currency:
- **CHF**: CH80 0078 1624 8968 1200 0
- **EUR**: CH53 0078 1624 8968 1200 1
- **USD**: CH26 0078 1624 8968 1200 2

## Re-syncing after edits

If you open the generated `.docx` in Word and edit it, run `/invoice-gdrive-sync [NUMBER]` to regenerate the PDF and overwrite the Drive folder.

## EU Member States (for reverse charge)

Austria, Belgium, Bulgaria, Croatia, Cyprus, Czech Republic, Denmark, Estonia, Finland, France, Germany, Greece, Hungary, Ireland, Italy, Latvia, Lithuania, Luxembourg, Malta, Netherlands, Poland, Portugal, Romania, Slovakia, Slovenia, Spain, Sweden.
