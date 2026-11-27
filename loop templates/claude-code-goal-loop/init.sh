#!/usr/bin/env bash
# Scaffold the Claude Code goal loop into a project directory.
#   init.sh <dir> [--web]     copy the template (never overwrites existing files); --web adds tools/shot.mjs
#   init.sh <dir> --check     list unfilled {{placeholders}} and missing pieces
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; T="$HERE/template"
DIR="${1:?usage: init.sh <dir> [--web|--check]}"; MODE="${2:-}"
mkdir -p "$DIR"; cd "$DIR"
FILES="CLAUDE.md .ai/project.md .ai/tasks.md .ai/handoff.md .ai/decisions.md .claude/settings.json .claude/hooks/loop-hook.mjs run-loop.sh tools/loop.mjs"

if [[ "$MODE" == "--check" ]]; then
  rc=0
  for f in $FILES; do [[ -f "$f" ]] || { echo "MISSING $f"; rc=1; }; done
  if grep -rn '{{' CLAUDE.md .ai/ 2>/dev/null; then echo "^ unfilled placeholders"; rc=1; fi
  grep -q 'Done when' .ai/tasks.md || { echo "tasks.md has no 'Done when' lines"; rc=1; }
  [[ -x run-loop.sh ]] || { echo "run-loop.sh is not executable"; rc=1; }
  command -v node >/dev/null || { echo "node not found (hooks and tools/loop.mjs need it)"; rc=1; }
  [[ -d .git ]] || echo "note: not a git repo yet (task-complete needs one)"
  [[ $rc == 0 ]] && echo "OK: loop files complete"
  exit $rc
fi

copy() { mkdir -p "$(dirname "$2")"; if [[ -e "$2" ]]; then echo "skip (exists): $2"; else cp -p "$1" "$2"; echo "created: $2"; fi; }
for f in $FILES; do copy "$T/$f" "$f"; done
if [[ -e .gitignore ]]; then grep -qxF '.ai/loop/' .gitignore || cat "$T/gitignore" >> .gitignore; echo "updated: .gitignore"; else copy "$T/gitignore" .gitignore; fi
if [[ "$MODE" == "--web" ]]; then copy "$T/tools/shot.mjs" tools/shot.mjs; fi
sed -i "s/{{DATE}}/$(date +%F)/" .ai/decisions.md
echo "next: fill the {{placeholders}}, then: $0 $DIR --check"
