# Invoice Spec Schema

JSON spec passed to `generate-invoice.py --spec-file <path>` (non-interactive mode). Used by the CoS email loop on Metis and by any automation that needs to drive the generator without interactive prompts.

## Shared fields (both types)

| Field | Type | Required | Notes |
|---|---|---|---|
| `type` | `"nipo"` or `"standard"` | yes | Dispatch key |
| `invoice_number` | string | yes | 5 digits, no hyphen (e.g. `"26016"`) |
| `invoice_date` | string | yes | `"2026-05-02"` or `"02 May 2026"` |
| `currency` | `"CHF"`, `"EUR"`, or `"USD"` | yes | Selects IBAN |
| `recipient` | object | yes | `{company, name, street, city, country}` |
| `abbrev` | string | yes | Short identifier for the Drive folder (`"KIEP"`, `"IADB"`). Never auto-derived. |
| `sync` | bool | no | Default `true`. `false` generates `.docx` only, skips PDF + Drive. |

## NIPO extras (`type: "nipo"`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `tier` | `"regular"`, `"academic_library"`, `"academic_student"` | yes | Picks template + defaults |
| `amount` | number | yes | e.g. `7000`. Overrides tier default only if explicitly set. |
| `subscription_period` | string | yes | `"May 2026 - April 2027"` — space-hyphen-space, full `Month YYYY` on both sides |

### NIPO example

```json
{
  "type": "nipo",
  "invoice_number": "26016",
  "invoice_date": "2026-05-02",
  "currency": "CHF",
  "amount": 1250,
  "tier": "academic_library",
  "subscription_period": "May 2026 - April 2027",
  "abbrev": "KIEP",
  "recipient": {
    "company": "Korea Institute for International Economic Policy",
    "name": "Seungrae Lee",
    "street": "246 Yangjae-daero, Seocho-gu",
    "city": "Seoul 06797",
    "country": "South Korea"
  }
}
```

## Standard extras (`type: "standard"`)

| Field | Type | Required | Notes |
|---|---|---|---|
| `subject_line` | string | yes | Project title — shows on invoice line (e.g. `"GTA Policy Intelligence Dashboard"`) |
| `intro_paragraph` | string | yes | 1–3 sentences; first sentence should reference the agreement |
| `items` | array of objects | yes | See below |
| `items_type` | `"deliverable"` or `"hours"` | yes | Selects rendering of items |
| `total` | number | yes | Invoice total |
| `vat_note` | string | no | Default `"No VAT is applied."` EU clients add `" The reverse charge mechanism applies."` |

### Items shape

- Deliverable: `[{"description": "...", "amount": 12000}, ...]`
- Hours: `[{"description": "Johannes Fritz", "hours": 45, "rate": 300, "total": 13500}, ...]`

### Standard example

```json
{
  "type": "standard",
  "invoice_number": "26016",
  "invoice_date": "2026-05-02",
  "currency": "CHF",
  "abbrev": "BORUSAN",
  "subject_line": "GTA Policy Intelligence Dashboard — Year 2",
  "intro_paragraph": "In accordance with our Advisory Agreement dated 12 February 2026, we hereby issue an invoice for the year-2 subscription of the GTA Policy Intelligence Dashboard.",
  "items": [
    {"description": "GTA Dashboard — Year 2 Subscription", "amount": 60000}
  ],
  "items_type": "deliverable",
  "total": 60000,
  "vat_note": "No VAT is applied.",
  "recipient": {
    "company": "Borusan Holding A.Ş.",
    "name": "Ayla Demir",
    "street": "Meclisi Mebusan Cad. No:37",
    "city": "34427 Istanbul",
    "country": "Turkey"
  }
}
```

## Invariants (also in `rules/invoice-governance.md`)

- Invoice numbers are exactly 5 digits, no separator. `26015`, not `26-015`.
- `subscription_period` uses `" - "` (space-hyphen-space) and full `"Month YYYY"` on both sides.
- `invoice_date` is the actual send date unless explicitly stated otherwise.
- Post-generation verification (read back the .docx and check 9 fields) is MANDATORY for NIPO; strongly recommended for standard.
