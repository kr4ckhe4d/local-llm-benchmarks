#!/usr/bin/env bash
# Can each router preset actually drive Claude Code? A real agentic task, not a
# chat probe: a two-file repo with a failing test, and the model must read it,
# fix the bug with the Edit tool, run the test with Bash and report. Pass means
# the file on disk is fixed and the test passes afterwards. That covers
# everything that has broken before: the late system message (Qwen chat
# templates), tool-schema grammar (gpt-oss), and plain tool-call reliability.
#
#   ./claude-compat.sh               every 128k preset
#   ./claude-compat.sh <preset>...   just these
#
# Added 2026-10-06. claude-speed.sh measures latency on a no-tool prompt; this
# measures whether the loop works at all, and what a real task costs.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
LAUNCH="$HERE/../claude-local.sh"
ROUTER="${ROUTER:-http://127.0.0.1:8090}"
OUT="${OUT:-$HERE/claude-compat.txt}"
TIMEOUT="${TIMEOUT:-1200}"
TASK="The test in test_calc.py fails. Find the bug, fix it with the Edit tool, then run the test with Bash (python3 test_calc.py) to confirm it passes. Reply with one line saying what you changed."
export ROUTER

presets() {
  curl -sS --max-time 15 "$ROUTER/v1/models" \
    | python3 -c 'import sys,json;[print(m["id"]) for m in json.load(sys.stdin)["data"]]' \
    | grep -E -- '-128k$' | sort
}

fixture() {  # fresh repo with one deliberate bug
  local d; d=$(mktemp -d "${TMPDIR:-/tmp}/claude-compat.XXXXXX")
  printf 'def add(a, b):\n    return a - b\n' > "$d/calc.py"
  printf 'from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n\nif __name__ == "__main__":\n    test_add()\n    print("ok")\n' > "$d/test_calc.py"
  echo "$d"
}

[ $# -gt 0 ] && LIST="$*" || LIST="$(presets)"
{
  printf '# Claude Code compatibility -- one real fix-the-bug task per preset\n'
  printf '# %s | claude %s | llama.cpp %s\n' "$(date -Is)" "$(claude --version 2>/dev/null | head -1)" \
    "$("$HOME/llama.cpp/build/bin/llama-server" --version 2>&1 | head -1)"
  printf '%-30s %-5s %6s %8s %8s  %s\n' preset pass turns api_s in_tok "result / error"
} | tee "$OUT"

for m in $LIST; do
  d=$(fixture)
  raw=$(cd "$d" && timeout "$TIMEOUT" "$LAUNCH" "$m" -p "$TASK" --output-format json \
        --dangerously-skip-permissions 2>&1)
  mkdir -p "$HERE/raw"; printf '%s' "$raw" > "$HERE/raw/compat-${m}.$(date +%s).txt"
  if (cd "$d" && python3 test_calc.py >/dev/null 2>&1); then pass=yes; else pass=NO; fi
  python3 - "$m" "$pass" "$raw" <<'PY' | tee -a "$OUT"
import sys, json
m, ok, raw = sys.argv[1], sys.argv[2], sys.argv[3]
d = None
for line in raw.splitlines():           # the JSON envelope is the last {...} line
    line = line.strip()
    if line.startswith("{") and '"session_id"' in line:
        try: d = json.loads(line)
        except Exception: pass
if d is None:
    print(f"{m:30} {ok:5} {'-':>6} {'-':>8} {'-':>8}  no envelope: {raw.strip().splitlines()[-1][:70] if raw.strip() else 'empty'}")
else:
    res = str(d.get("result") or d.get("api_error_status") or "").replace("\n", " ")
    err = " ERROR" if d.get("is_error") else ""
    print(f"{m:30} {ok:5} {d.get('num_turns', 0):>6} {d.get('duration_api_ms', 0)/1000:>8.1f} "
          f"{d.get('usage', {}).get('input_tokens', 0):>8}  {res[:80]}{err}")
PY
  rm -rf "$d"
done
