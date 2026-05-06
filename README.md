# cc-sgept-backoffice

SGEPT back-office capabilities: invoice generation (NIPO + standard), templates, and the agent/prompt surface used by both the CEO's local slash commands and the Chief-of-Staff email loop on Metis.

## How this stacks

This repo is the **back-office automation engine** for SGEPT invoicing. Dependencies:

- **(required)** Python + python-docx + Pillow + (macOS: docx2pdf + Word, Linux: libreoffice) for invoice rendering
- **(required)** Google Drive access — either the macOS Drive File Stream mount (canonical jf-private layout via SGEPT_GDRIVE_INVOICING env var, defaults to `~/Library/CloudStorage/...`) OR the Google Drive API via `mcp-google-workspace/service-account.json` on Linux
- **(required)** SGEPT bank account config + NIPO Stripe link config (in `config/` directory)
- **(optional companion)** cc-os — provides session-tracking, `/handoff`. Invoice flows work without cc-os.

The repo IS structurally tied to the canonical jf-private layout: invoice folders land at `jf-ceo/sgept-backoffice/invoicing/YYMMDD [Descriptor] {NUMBER}/`, the sequential-numbering rule scans that path, and the symlink targets in /jf-ceo/sgept-backoffice/ are the canonical work directory. Standalone consumers would need to provide an equivalent target tree and override `SGEPT_GDRIVE_INVOICING`.

## Contents

| Dir | Purpose |
|---|---|
| `agents/` | Back-office agent definitions (future) |
| `commands/` | Slash commands (`/invoice`, `/invoice-nipo`, `/invoice-gdrive-sync`) symlinked into `jf-ceo/.claude/commands/` |
| `prompts/` | Prompt fragments consumed by the CoS inbox loop (`invoice-handler.md`) |
| `scripts/` | `generate-invoice.py`, `pdf_convert.py`, `gdrive_upload.py` — cross-platform (macOS + Linux) |
| `templates/invoices/` | SGEPT invoice `.docx` templates (NIPO regular/academic_library/academic_student, standard) |
| `config/` | `bank-accounts.json`, `nipo-stripe-links.json` |
| `knowledge/` | Spec schemas, field reference docs |
| `rules/` | Invoice governance (invariants, verification checklist) |

## Install

### jf-ceo (local, interactive)

```bash
# From jf-private root after cloning this repo into claude-setup/:
ln -s ../../../claude-setup/cc-sgept-backoffice/scripts/generate-invoice.py \
      jf-ceo/sgept-backoffice/scripts/generate-invoice.py
ln -s ../../../claude-setup/cc-sgept-backoffice/templates/invoices \
      jf-ceo/sgept-backoffice/templates/invoices
ln -s ../../../../claude-setup/cc-sgept-backoffice/config \
      jf-ceo/sgept-backoffice/invoicing/config
for f in invoice invoice-nipo invoice-gdrive-sync; do
  ln -s ../../../claude-setup/cc-sgept-backoffice/commands/${f}.md \
        jf-ceo/.claude/commands/${f}.md
done
```

### Metis server (autonomous, via CoS)

`cc-sgept-backoffice` is cloned by `jf-private/scripts/setup-repos.sh` on initial deploy. Subsequent updates arrive via `pull-all.sh` (runs at the start of every CoS cron invocation).

## Platform requirements

| Platform | PDF backend | Drive upload backend |
|---|---|---|
| macOS | `docx2pdf` + Microsoft Word (AppleScript) | Drive File Stream mount |
| Linux (Metis) | `libreoffice --headless --convert-to pdf` | Google Drive API via `mcp-google-workspace/service-account.json` |

## Canonical paths

- Generated invoice folders: `jf-ceo/sgept-backoffice/invoicing/YYMMDD [Descriptor] {NUMBER}/`
- Google Drive root folder id (5 invoicing): `19bPRghIb2L3cdxZzIattO65uM5En6dHM`
