---
description: Collect monthly consultant invoices from Gmail and forward to Mrs Peterhans
---

Collect consultant invoices for the specified month and prepare them for accounting.

**Target month:** $ARGUMENTS (e.g. "March 2026", "2603"). If empty, ask the user.

**Protocol:** Read and follow `sgept-backoffice/invoicing/PROTOCOL.md` — it is the authoritative reference for consultant list, search queries, naming conventions, email templates, and edge cases.

**Output folder:** `sgept-backoffice/bills/consultants/YYMM/` (e.g. `2603/` for March 2026).

## Execution

### Phase 1: Setup
1. Read `sgept-backoffice/invoicing/PROTOCOL.md` for the full consultant list and procedure.
2. Create the month folder: `sgept-backoffice/bills/consultants/YYMM/`
3. Check for an existing checklist at `sgept-backoffice/bills/consultants/YYMM/checklist.md`. If one exists, resume from where it left off.

### Phase 2: Search and Download
4. Search **office@sgept.org** Gmail (`google-office` MCP) for invoices from each consultant using the search patterns in the protocol.
5. Also search for unread consultant emails with attachments (catches late invoices from prior months — see protocol Step 3b).
6. Download each invoice attachment using `gmail_downloadAttachment`.
7. Save to `sgept-backoffice/bills/consultants/YYMM/` using naming convention: `Last name, First name - YYMM.pdf`

### Phase 3: Process
8. For each processed invoice email: mark as read and **send** a thank-you reply directly ("Thank you very much, invoice received. Johannes"). Thank-you replies are routine — send them immediately, do not draft. Use `gmail_send` with `threadId` to reply in-thread. For consultants with multiple invoices (e.g. Angelo Gerber-Helm sends GTA + DPA separately), reply to **each** thread.
9. For non-PDF submissions: accept the file but send a reply with a polite PDF format reminder (see protocol Step 5).
10. For late invoices from prior months: save to the correct month folder (`YYMM` based on invoice content, not email date).

### Phase 4: Compile for Accounting
11. Create/update checklist at `sgept-backoffice/bills/consultants/YYMM/checklist.md` with status of all 20 consultants.
12. **Send** email to `corinne.peterhans@kropftreuhand.ch` with **CC `johannes.fritz@sgept.org`** via **office@sgept.org** in German — subject: `Consultant Rechnungen [German month] [Year]`. Follow the template in protocol Step 7. Use `send_threaded_reply.py --account office` (set `"cc": "johannes.fritz@sgept.org"` in the send-list JSON; include `"attachments": [...]` with all downloaded PDFs, including late invoices from prior months). **IMPORTANT:** The script treats the body as HTML when attachments are present — format the body with `<p>`, `<ol>`, `<li>`, `<br>` tags (not plain text). Auto-send (no `--draft`) — the CC to johannes ensures CEO visibility; sentinel file `forwarded-on-DD.txt` in the month folder prevents double-send on re-run.
13. List received and missing invoices in the email body.

### Phase 5: Follow Up
14. For missing invoices: **send** reminder emails directly (see protocol Step 9).
15. If this is a second run (>7th of the month) and invoices are still missing: use the escalation template (protocol Step 12).

## Key Constraints
- **Gmail account:** Use `google-office` MCP (office@sgept.org) for searches and replies. Use `send_threaded_reply.py --account office` for sending with attachments.
- **Naming:** `Last name, First name - YYMM.pdf` — no exceptions.
- **Month assignment:** Based on invoice content, not email date.
- **Thank-you replies:** Send directly (not draft). These are routine.
- **Peterhans email:** Auto-sent with CC `johannes.fritz@sgept.org`. Sentinel file `bills/consultants/YYMM/forwarded-on-DD.txt` is written after send; on re-run, check for this sentinel before sending again to avoid duplicates.
- **Reminders:** Send directly.

## Idempotency

The cron variant of this routine (`jf-metis/scripts/run-invoice-routine-cron.sh`) writes sentinels in the month folder after each authoritative send: `forwarded-on-DD.txt` (the 5th-of-month send), `supplementary-on-DD.txt` (late-arrival forwards), `reminder-sent.txt` (7th-of-month reminders), and `escalation-sent.txt` (14th-of-month escalation). Always check these before sending — they are the source of truth for "this has already been done this month." The interactive slash command should respect the same sentinels.

## Output Summary
When done, report:
1. How many invoices collected (X of 20)
2. Which consultants are still missing
3. Thank-you replies sent (count)
4. Peterhans email sent to `corinne.peterhans@kropftreuhand.ch` (cc johannes), with sentinel written
5. Reminders sent for missing invoices (count)
