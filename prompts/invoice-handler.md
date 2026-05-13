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

## STEP A — Classify the turn (using thread context)

Read `thread_history` from the inbound JSON. Treat every prior turn — CEO message AND Metis reply alike — as authoritative context for the current request. Do NOT call any Gmail MCP tool; none is available in this loop. If `thread_history` is missing or empty, treat the current `body_text` as the sole context (degraded path — older imap-fetch.py builds).

Is this a **new invoice request**, an **iteration on an existing draft**, or an **approval**?

- **New:** no prior Metis reply in `thread_history` attached an invoice PDF and the JFM team has no live `cos-meta: thread=<this_thread_id>` marker. Proceed to STEP A.1 (Spawn-or-inline routing).
- **Iteration:** either (a) a prior Metis reply attached a draft PDF, or (b) a JFM exists for this thread with state `cos:awaiting-approval` or `cos:awaiting-input`. Extract the invoice number from:
  1. The JFM description / `cos-meta:` markers if a JFM exists, or
  2. The subject line (`"Draft 26016..."`), or
  3. The prior Metis reply body (search for the 5-digit number), or
  4. The attachment filename.
  Then proceed to STEP A.1 (Spawn-or-inline routing) with the existing number.
- **Approval:** the CEO's latest body starts (first 200 chars, case-insensitive) with one of: `approve`, `approved`, `send it`, `ship it`, `finalize`, `looks good send it`. Proceed to STEP A.1 with `--final` intent.

If none match cleanly, reply asking for clarification. Do NOT generate.

## STEP A.1 — Spawn-or-inline routing (L4)

Once an invoice JFM workflow YAML exists at `cc-project-mgmt-team/workflows/invoice-nipo.yaml` AND `invoice-nipo` is in `spawn-claude-workflow.sh:ALLOWED_WORKFLOWS`, prefer the **spawn path**:

1. **New invoice:** Create a JFM issue on the JF-METIS team with:
   - Title: `[Invoice] <abbrev> <amount> <currency> — <recipient.company>` (placeholders filled from STEP B.0 extraction below; if extraction is partial, use what you have plus `?` for gaps).
   - Description: a single fenced block beginning with `cos-meta: thread=<gmail_thread_id> msgid=<initial_msgid>`, followed by a YAML spec block (`recipient`, `tier`, `amount`, `currency`, `invoice_number`, `subscription_period`, `abbrev`).
   - First comment: `cos-meta: thread-history` followed by the full `thread_history` JSON snapshot.
   Then call `bash $METIS_DIR/scripts/spawn-claude-workflow.sh invoice-nipo $WORKSPACE JFM-N` and EXIT this handler — the detached workflow will run the extraction, generate the draft, and reply in-thread.

2. **Iteration / approval on existing JFM:** Look up the JFM by `cos-meta: thread=<thread_id>` marker via `linear-api.py list-issues --team JFM --query "<thread_id>"`. Append the new CEO reply to the `cos-meta: thread-history` comment (replace in place — keep only the latest snapshot). Then call `spawn-claude-workflow.sh invoice-nipo $WORKSPACE JFM-N` and EXIT.

3. **Fallback (inline path):** If the workflow YAML or whitelist entry is not yet present (transitional period before L4 lands), continue inline with STEP B.0 below. The same extraction + one-shot confirmation + generation steps apply.

## STEP B — Pick the next invoice number

```bash
ls /home/deploy/jf-private/jf-ceo/sgept-backoffice/invoicing/ | grep -oE ' [0-9]{5}$' | tr -d ' ' | sort -n | tail -1
```

Add 1. That's the next number. If the max is `26015`, the next is `26016`. (If the CEO specified a number explicitly in their request, use that and skip this step.)

## STEP B.0 — Extract everything you can in one pass

**Before** asking the CEO anything, run a single structured extraction over `body_text` PLUS every entry in `thread_history`. Build the spec object with as many fields populated as the text supports. Apply these inference rules:

- **Address extraction** — recognise these postal patterns:
  - German DE: 5-digit postcode + city (e.g. `68161 Mannheim`) → country = Germany
  - Swiss CH: 4-digit postcode + city (e.g. `9010 St.Gallen`) → country = Switzerland
  - US: 5-digit ZIP + 2-letter state (e.g. `02139 MA`) → country = United States
  - UK: alphanumeric postcode (e.g. `EC1A 1BB`) → country = United Kingdom
  - Fall back to ask only if no postcode is present anywhere in the thread.
- **Tier inference from amount when explicit:** CHF/EUR/USD `500` ⇒ `academic_student`; `1250` ⇒ `academic_library`; `7000` ⇒ `regular`. If amount is ambiguous, ask.
- **Period default per tier** (apply when CEO did not specify a range):
  - `regular` → 12 months from invoice date
  - `academic_library` → 12 months from invoice date
  - `academic_student` → invoice month only (`period_start == period_end`, e.g. `"May 2026 - May 2026"`)
- **Abbreviation: derive, don't ask.** Take the first all-caps token (≥2 chars) from the institution name; fall back to first 4 letters of the first word. Treat the result as a PROPOSAL the CEO can override in the confirmation reply, never as a blocking question.
- **Contact name:** match `Prof.|Dr.|Mr.|Ms.|Mrs.` + name; or any named addressee in the forwarded body.

## STEP C — Confirm or generate (one-shot)

After STEP B.0, decide:

- **Spec is complete** (all of: invoice_number, tier, amount, currency, recipient.{company, name, street, city, country}, subscription_period; abbrev derived): proceed to STEP D and generate. The confirmation happens implicitly via the draft PDF in the reply — the CEO either approves or corrects.

- **Spec has gaps:** reply ONCE with a single confirmation message containing (a) a structured summary of every field you parsed, (b) the explicit list of gaps you need filled, (c) the closing line *"Reply 'go' to generate as shown, or correct any field."* Do NOT enter a multi-turn interrogation loop. Set the JFM state to `cos:awaiting-input` and exit. The CEO's next reply will arrive with the full `thread_history` attached and the next spawn will re-run STEP B.0 with the additional information.

Required fields for generation:

**Common:**
- `type`: `"nipo"` or `"standard"` (infer from body; ask if ambiguous)
- `invoice_date`: today's date as `YYYY-MM-DD` unless explicitly specified
- `currency`: `"CHF"`, `"EUR"`, or `"USD"`
- `recipient`: `{company, name, street, city, country}` — all five required, no partial
- `abbrev`: short identifier for the Drive folder — auto-derived per STEP B.0; included in confirmation summary so CEO can override

**NIPO-specific:**
- `tier`: `"regular"`, `"academic_library"`, `"academic_student"`
- `amount`: number (default to tier default: 7000 / 1250 / 500)
- `subscription_period`: `"Month YYYY - Month YYYY"` per the tier default unless overridden (space-hyphen-space, full Month YYYY on both sides; equal start/end is valid for one-off academic_student)

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
- **ALWAYS propose the abbreviation; never block on it.** Derive per STEP B.0 (first all-caps token in company name, fall back to first 4 letters of first word). Include it in the confirmation summary so the CEO can override — but a missing/unconfirmed abbrev is NOT a reason to refuse generation. The Drive folder name uses this value, and an override-via-rename is easy.
- **ALWAYS use --no-sync** in `generate-invoice.py` during iteration. Drive upload only on finalization.
- **NEVER interrogate field-by-field.** If the spec has gaps after STEP B.0, reply ONCE with the confirmation summary + gap list. Multi-turn questioning is forbidden: every round-trip risks dropping context.
- **NEVER use a Gmail MCP tool.** None is available in this loop. Use `thread_history` from the inbound JSON for prior-turn context.
- **Governance rules** in `rules/invoice-governance.md` are blocking: any rule violation = stop and report.
