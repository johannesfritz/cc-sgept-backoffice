# Invoice Handler (CoS inbox)

Prompt fragment included by `metis-cos-inbox.md` when a CEO email looks like an invoice request. Assumes the outer prompt has already verified the sender.

## When to use this handler

The email body contains ONE OR MORE of:

- A clear invoice intent ("invoice", "bill", "NIPO invoice", "send invoice for", "create invoice").
- An amount + currency + recipient (strongly suggests invoicing).
- A reply in a thread where the previous CoS turn attached a draft invoice PDF.

If none of these apply, fall back to the general CoS handler.

## Path constants (server-side)

- Generator: `/home/deploy/jf-private/claude-setup/cc-sgept-backoffice/scripts/generate-invoice.py`
- Drive upload: `/home/deploy/jf-private/claude-setup/cc-sgept-backoffice/scripts/gdrive_upload.py`
- Notify reply: `/home/deploy/jf-private/jf-metis/scripts/notify-reply.py`
- Invoice output root: `/home/deploy/jf-private/jf-ceo/sgept-backoffice/invoicing/`
- Spec schema: `/home/deploy/jf-private/claude-setup/cc-sgept-backoffice/knowledge/invoice-spec-schema.md`
- Governance invariants: `/home/deploy/jf-private/claude-setup/cc-sgept-backoffice/rules/invoice-governance.md`

Read the schema + invariants before classifying. The invariants are NOT negotiable.

## STEP A — Classify the turn

Is this a **new invoice request** or an **iteration on an existing draft**?

Use `mcp__claude_ai_Gmail__gmail_read_thread` with the message ID or thread to see prior turns.

- **New:** no prior CoS reply in the thread attached an invoice PDF. Proceed to STEP B.
- **Iteration:** a prior CoS reply attached a draft PDF. Extract the invoice number from:
  1. The subject line if present (`"Draft 26016..."`), or
  2. The prior CoS reply body (search for the 5-digit number), or
  3. The attachment filename.
  Then proceed to STEP E with the existing number.
- **Approval:** the CEO's body starts (first 200 chars, case-insensitive) with one of: `approve`, `approved`, `send it`, `ship it`, `finalize`, `looks good send it`. Proceed to STEP F with the existing invoice number.

If none of these match cleanly, reply asking for clarification. Do NOT generate.

## STEP B — Pick the next invoice number

```bash
ls /home/deploy/jf-private/jf-ceo/sgept-backoffice/invoicing/ | grep -oE ' [0-9]{5}$' | tr -d ' ' | sort -n | tail -1
```

Add 1. That's the next number. If the max is `26015`, the next is `26016`.

## STEP C — Extract fields from the email

Required fields (refuse to generate until all are present — reply asking for the gaps):

**Common:**
- `type`: `"nipo"` or `"standard"` (infer from body; ask if ambiguous)
- `invoice_date`: today's date as `YYYY-MM-DD` unless explicitly specified
- `currency`: `"CHF"`, `"EUR"`, or `"USD"`
- `recipient`: `{company, name, street, city, country}` — all five required, no partial
- `abbrev`: short identifier for the Drive folder. If the CEO didn't provide one, ASK — never auto-derive.

**NIPO-specific:**
- `tier`: `"regular"`, `"academic_library"`, `"academic_student"`
- `amount`: number (default to tier default: 7000 / 1250 / 500 — confirm if unstated)
- `subscription_period`: `"Month YYYY - Month YYYY"` (space-hyphen-space, full Month YYYY on both sides)

**Standard-specific:**
- `subject_line`: project title
- `intro_paragraph`: 1–3 sentences (draft from the email's service description)
- `items`: array of `{description, amount}` (deliverable) or `{description, hours, rate, total}` (hours)
- `items_type`: `"deliverable"` or `"hours"`
- `total`: sum of items
- `vat_note`: default `"No VAT is applied."`; EU recipients append `" The reverse charge mechanism applies."`

## STEP D — Generate the invoice (new)

Write the spec to a tmpfs file, then call the generator WITHOUT Drive sync:

```bash
cat > /dev/shm/invoice-spec.{{PID}}.json <<'JSON'
{
  "type": "nipo",
  "invoice_number": "26016",
  "invoice_date": "2026-04-17",
  "currency": "CHF",
  "amount": 1250,
  "tier": "academic_library",
  "subscription_period": "May 2026 - April 2027",
  "abbrev": "KIEP",
  "recipient": {"company": "...", "name": "...", "street": "...", "city": "...", "country": "..."},
  "sync": false
}
JSON

python3 /home/deploy/jf-private/claude-setup/cc-sgept-backoffice/scripts/generate-invoice.py \
  --spec-file /dev/shm/invoice-spec.{{PID}}.json --no-sync
```

`--no-sync` keeps Drive upload out of the critical path (the iteration happens via git/attachment). Final upload is in STEP F.

The generator prints `INVOICE_OUTPUT: <path>.docx`. Capture that path.

Convert to PDF:

```bash
python3 /home/deploy/jf-private/claude-setup/cc-sgept-backoffice/scripts/pdf_convert.py <docx_path>
```

This prints `PDF_OUTPUT: <path>.pdf`. Verify size >1KB.

**Verify the invoice** (mandatory for NIPO per `rules/invoice-governance.md`): read back the `.docx` with `python-docx` and check the 9-item list from the governance rules. If any check fails, stop — reply with the exact mismatch, do not send the draft.

## STEP E — Iterate on an existing draft

Read the `.docx`/`.pdf` at `jf-ceo/sgept-backoffice/invoicing/<folder-ending-in NUMBER>/`. Regenerate with the amended fields. Overwrite the existing files. Same verification as STEP D.

If the amendment is trivial text-only (e.g. "typo in street"), prefer a minimal regeneration — same invoice number, same folder, updated field only.

## STEP F — Finalize (on "approve")

1. **Verify once more.** Read back the `.docx`, run the 9-point check.
2. **Upload to Drive:**
   ```bash
   python3 /home/deploy/jf-private/claude-setup/cc-sgept-backoffice/scripts/gdrive_upload.py \
     --number NUMBER --abbrev ABBREV --docx <docx_path> [--nipo]
   ```
   If this fails with a Drive-API-disabled error, capture the error; do NOT abort. Proceed to git commit and include the failure note in the reply (CEO resolves manually via `/invoice-gdrive-sync`).
3. **Git commit + push** (both repos if applicable):
   ```bash
   cd /home/deploy/jf-private
   git add jf-ceo/sgept-backoffice/invoicing/<folder>
   git commit -m "Invoice NUMBER: ABBREV final (via CoS)"
   git push
   ```
4. Reply confirming finalization — include the Drive URL if upload succeeded, or a "Drive upload pending" note if not.

## Reply template

For a new draft:
```
Draft <NUMBER> attached for review.
<one-line summary: type, recipient, amount, period/subject>
Reply "approve" to finalize, or describe changes.
— Metis
```

For an iteration:
```
Revised draft <NUMBER> attached.
Changed: <brief summary of what changed>
Reply "approve" to finalize, or describe more changes.
— Metis
```

For finalization (success):
```
Invoice <NUMBER> filed.
Drive: <url>
Local: git pull to sync jf-private on your Mac.
— Metis
```

For finalization (Drive failure):
```
Invoice <NUMBER> committed to git (git pull on your Mac to sync).
Drive upload failed: <short error>. Run /invoice-gdrive-sync <NUMBER> locally to push to Drive.
— Metis
```

## Attaching the PDF in the reply

Use `notify-reply.py --attach`:

```bash
printf '%s' "Draft <NUMBER> attached..." > /dev/shm/metis-cos-reply.<uid>.{{PID}}.txt
python3 /home/deploy/jf-private/jf-metis/scripts/notify-reply.py \
  --in-reply-to '<message_id>' \
  --references '<references string>' \
  --subject 'Re: <original subject>' \
  --body-file /dev/shm/metis-cos-reply.<uid>.{{PID}}.txt \
  --to '<from_addr>' \
  --attach '<pdf_path>'
```

## Hard constraints

- **NEVER send an invoice without verification.** If verification fails, reply with the failure, do not attach a bad PDF.
- **NEVER commit/push without "approve".** Iteration drafts stay uncommitted on Metis disk only.
- **NEVER guess the abbreviation.** If the CEO didn't give one, ask.
- **ALWAYS use --no-sync** in `generate-invoice.py` during iteration. Drive upload only on finalization.
- **Governance rules** in `rules/invoice-governance.md` are blocking: any rule violation = stop and report.
