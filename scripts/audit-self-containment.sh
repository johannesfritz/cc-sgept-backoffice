#!/usr/bin/env bash
# audit-self-containment.sh — fail if this repo has hard machine-local paths
# or unqualified cross-repo / cross-workspace references.
#
# Run from the repo root:
#   bash scripts/audit-self-containment.sh
#
# Exits 0 if clean, 1 if any forbidden pattern is found. Permitted forms:
#   - References prefixed with "(optional companion)" or "**(optional companion)**"
#   - References prefixed with "(required companion)" or "**(required companion)**"
#   - Lines containing one of the framing tokens:
#       (example) | canonical jf-private layout | case study | illustrative
#   - Self-references (this repo's own name)
#   - Lines inside this audit script itself
#
# Scope: only tracked files (uses `git ls-files`), so .gitignored derived
# outputs are not scanned. Restricts to text formats: .md .yaml .yml .json
# .py .sh .toml .txt .

set -o errexit
set -o pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

REPO_NAME="$(basename "$REPO_ROOT")"
SCRIPT_RELPATH="scripts/audit-self-containment.sh"
PERMITTED_FRAMING='optional companion|required companion|\(example\)|canonical jf-private layout|case study|illustrative'

# Tracked text files only. Bash 3-compatible array construction (no mapfile).
# Per-file exemptions: files in `.audit-canonical-layout` are intrinsically
# about the canonical jf-private layout (manifests, architecture docs, layout
# rules) — references inside them are by-design, not portability bugs.
EXEMPT_FILE=".audit-canonical-layout"
exempt_re=""
if [ -f "$EXEMPT_FILE" ]; then
  exempt_re=$(grep -vE '^\s*(#|$)' "$EXEMPT_FILE" | tr '\n' '|' | sed 's/|$//')
fi

files=()
while IFS= read -r line; do
  if [ -n "$exempt_re" ] && [[ "$line" =~ ^($exempt_re)$ ]]; then
    continue
  fi
  files+=("$line")
done < <(git ls-files \
  '*.md' '*.yaml' '*.yml' '*.json' '*.py' '*.sh' '*.toml' '*.txt' \
  | grep -v "^${SCRIPT_RELPATH}$" \
  || true)

if [ ${#files[@]} -eq 0 ]; then
  echo "OK: $REPO_NAME has no tracked text files to scan."
  exit 0
fi

fail=0

check_pattern() {
  local label="$1"; shift
  local pattern="$1"; shift
  local hits
  hits=$(grep -nE "$pattern" "${files[@]}" 2>/dev/null \
    | grep -vE "$PERMITTED_FRAMING" \
    || true)
  if [ -n "$hits" ]; then
    echo "FAIL: $label"
    echo "$hits" | sed 's/^/  /'
    echo ""
    fail=1
  fi
}

# 1. Hard-coded user paths.
check_pattern "hard-coded \$HOME path"   '~/Documents/GitHub/jf-private'
check_pattern "hard-coded /Users/ path"  '/Users/[a-zA-Z0-9_.-]+/'

# 2. Cross-workspace references to jf-* trees.
for ws in jf-ceo jf-dev jf-thought jf-metis jf-private; do
  check_pattern "unqualified $ws reference" "(^|[^/a-z-])$ws/"
done

# 3. Cross-repo references to other cc-* repos (excluding self).
# Exclude any line containing the self-name as a substring — handles
# both the bare form (cc-os) and compound forms (cc-os-side, cc-os-config-*,
# johannesfritz-cc-os, etc.). False-negative risk: lines mixing self-name +
# a real cross-repo ref get exempted entirely; that ref still needs framing
# but won't be flagged here. Acceptable trade-off.
hits=$(grep -nE 'cc-[a-z][a-z0-9-]+' "${files[@]}" 2>/dev/null \
  | grep -vE "${REPO_NAME}" \
  | grep -vE "$PERMITTED_FRAMING" \
  || true)
if [ -n "$hits" ]; then
  echo "FAIL: unqualified cross-repo cc-* reference"
  echo "$hits" | sed 's/^/  /'
  echo ""
  fail=1
fi

if [ $fail -eq 0 ]; then
  echo "OK: $REPO_NAME passes self-containment audit (${#files[@]} files checked)."
  exit 0
fi

echo "Add an '(optional companion)', '(required companion)', '(example)',"
echo "'canonical jf-private layout' or '(case study)' qualifier on the line,"
echo "OR remove the reference."
exit 1
