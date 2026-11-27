#!/usr/bin/env bash
# Scaffold the pi goal loop into a project directory.
#   init.sh <dir> [--web]     copy templates (never overwrites existing files)
#   init.sh <dir> --check     list unfilled {{placeholders}} and missing pieces
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; T="$HERE/template"
DIR="${1:?usage: init.sh <dir> [--web|--check]}"; MODE="${2:-}"
mkdir -p "$DIR"; cd "$DIR"

if [[ "$MODE" == "--check" ]]; then
  rc=0
  for f in AGENTS.md .ai/project.md .ai/tasks.md .ai/handoff.md .ai/decisions.md .pi/extensions/goal-loop.ts; do
    [[ -f "$f" ]] || { echo "MISSING $f"; rc=1; }
  done
  if grep -rn '{{' AGENTS.md .ai/ 2>/dev/null; then echo "^ unfilled placeholders"; rc=1; fi
  grep -q 'Done when' .ai/tasks.md || { echo "tasks.md has no 'Done when' lines"; rc=1; }
  [[ -d .git ]] || echo "note: not a git repo yet"
  [[ $rc == 0 ]] && echo "OK: loop files complete"
  exit $rc
fi

copy() { mkdir -p "$(dirname "$2")"; if [[ -e "$2" ]]; then echo "skip (exists): $2"; else cp "$1" "$2"; echo "created: $2"; fi; }
copy "$T/AGENTS.md" AGENTS.md
for f in project.md tasks.md handoff.md decisions.md; do copy "$T/.ai/$f" ".ai/$f"; done
copy "$T/.pi/extensions/goal-loop.ts" .pi/extensions/goal-loop.ts
if [[ -e .gitignore ]]; then grep -qxF '.ai/STOP' .gitignore || cat "$T/gitignore" >> .gitignore; echo "updated: .gitignore"; else copy "$T/gitignore" .gitignore; fi
if [[ "$MODE" == "--web" ]]; then copy "$T/tools/shot.mjs" tools/shot.mjs; fi
sed -i "s/{{DATE}}/$(date +%F)/" .ai/decisions.md
echo "next: fill the {{placeholders}}, then: $0 $DIR --check"
