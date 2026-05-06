#!/usr/bin/env bash
# cc-sgept-backoffice — Claude Code install script (standalone)
# Symlinks commands + agents + prompts + rules into .claude/.
# NOTE: invoice generation also requires the canonical jf-private layout's jf-ceo/sgept-backoffice/
# work directory to exist on disk (or override paths via SGEPT_GDRIVE_INVOICING
# env var + caller-supplied OUTPUT_DIR).

set -euo pipefail
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLUGIN_ROOT="$SCRIPT_DIR"
WORKSPACE_DIR="${CLAUDE_WORKSPACE_DIR:-$PWD}"
CLAUDE_DIR="$WORKSPACE_DIR/.claude"

echo "cc-sgept-backoffice installer"
echo "  plugin root:  $PLUGIN_ROOT"
echo "  target:       $CLAUDE_DIR"
[ -d "$WORKSPACE_DIR" ] || { echo "ERROR: workspace not found" >&2; exit 1; }

mkdir -p "$CLAUDE_DIR"/{commands,agents,prompts,rules}
shopt -s nullglob

for f in "$PLUGIN_ROOT/commands/"*.md; do ln -sfn "$f" "$CLAUDE_DIR/commands/$(basename "$f")"; echo "  command:  $(basename "$f")"; done
for f in "$PLUGIN_ROOT/agents/"*.md;   do ln -sfn "$f" "$CLAUDE_DIR/agents/$(basename "$f")";   echo "  agent:    $(basename "$f")"; done
for f in "$PLUGIN_ROOT/prompts/"*.md;  do ln -sfn "$f" "$CLAUDE_DIR/prompts/$(basename "$f")";  echo "  prompt:   $(basename "$f")"; done
for f in "$PLUGIN_ROOT/rules/"*.md;    do ln -sfn "$f" "$CLAUDE_DIR/rules/$(basename "$f")";    echo "  rule:     $(basename "$f")"; done

echo ""
echo "Install complete. Restart Claude Code (or /init); /invoice, /invoice-nipo, /invoice-gdrive-sync appear."
echo "External deps: python-docx, Pillow, docx2pdf|libreoffice, Google Drive access."
echo "Override paths: SGEPT_GDRIVE_INVOICING, INVOICE_OUTPUT_DIR (see scripts/generate-invoice.py)."
