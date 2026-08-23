#!/usr/bin/env bash
# Measure every router preset as Claude Code actually experiences it.
#
# This is not llama-bench. The Throughput table in README.md measures the model
# in isolation; this measures the number a person waits on, which includes a
# ~26k-token system prompt on every single turn. A model that generates fast
# but prefills slowly feels slow here, and that ordering is the point.
#
#   ./claude-speed.sh            all 128k presets
#   ./claude-speed.sh <preset>…  just these
#
# Each preset runs twice. Run 1 is cold: the router loads the model from disk
# and prefills from scratch. Run 2 is warm, with the prefix cached -- that is
# the steady-state turn. Both are reported because both are real.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
LAUNCH="$HERE/../claude-local.sh"
ROUTER="${ROUTER:-http://127.0.0.1:8090}"
OUT="${OUT:-$HERE/claude-harness-speed.txt}"
PROMPT="${PROMPT:-Write a Python function merge_sort(lst) with type hints and a short docstring. Output only code, no explanation.}"
TIMEOUT="${TIMEOUT:-1500}"

export ROUTER

models() {
  curl -sS --max-time 15 "$ROUTER/v1/models" \
    | python3 -c 'import sys,json;[print(m["id"]) for m in json.load(sys.stdin)["data"]]'
}

# One preset per distinct model, at the 128k tier -- the smallest that Claude
# Code can use at all. Testing every context tier would multiply the runtime
# without changing the ranking.
pick() {
  models | grep -E '(-128k|-128k)$' | sort
}

run_once() {   # preset -> "ttft_ms api_ms in_tok out_tok" or "ERR <msg>"
  local m="$1" raw js
  raw=$(timeout "$TIMEOUT" "$LAUNCH" "$m" -p "$PROMPT" --output-format json 2>&1)
  js=${raw#*\{}; js="{$js"
  # Keep the raw envelope. A derived number nobody can re-derive is a claim.
  mkdir -p "$HERE/raw"; printf '%s' "$js" > "$HERE/raw/${m}.$(date +%s).json"
  python3 - "$js" <<'PY' 2>/dev/null || echo "ERR unparseable"
import sys,json
try:
    d=json.loads(sys.argv[1])
except Exception:
    print("ERR unparseable"); raise SystemExit
if d.get("is_error") or d.get("api_error_status"):
    print("ERR "+str(d.get("api_error_status") or d.get("result",""))[:60]); raise SystemExit
u=d.get("usage",{})
print(f'{d.get("ttft_ms",0)} {d.get("duration_api_ms",0)} {u.get("input_tokens",0)} {u.get("output_tokens",0)}')
PY
}

[ $# -gt 0 ] && LIST="$*" || LIST="$(pick)"

{
  printf '# Claude Code harness speed -- what the client actually waits on\n'
  printf '# router : %s\n' "$ROUTER"
  printf '# prompt : %s\n' "$PROMPT"
  printf '# host   : %s, llama.cpp %s\n' "$(uname -sr)" \
    "$("$HOME/llama.cpp/build/bin/llama-server" --version 2>&1 | head -1)"
  printf '# date   : %s\n#\n' "$(date -Is)"
  printf '# COLD_s  first turn: router loads the model from disk, then prefills.\n'
  printf '# WARM_s  second identical turn, model resident -- the per-turn wait.\n'
  printf '# TTFT_s  time to first token. Prefill of the system prompt lives here.\n'
  printf '# GEN_s   WARM_s - TTFT_s: time actually spent emitting the answer.\n'
  printf '# IN_tok  prompt tokens re-processed EVERY turn (system + 30 tool schemas).\n'
  printf '#\n'
  printf '# No tok/s column on purpose. GEN_s is under a second for most rows, so\n'
  printf '# output_tokens/GEN_s divides by timing noise and produced figures 5-10x\n'
  printf '# the rates llama-bench measures. The raw envelopes are in raw/.\n\n'
  printf '%-30s %8s %8s %8s %8s %8s %8s\n' MODEL COLD_s WARM_s TTFT_s GEN_s IN_tok OUT_tok
  printf '%-30s %8s %8s %8s %8s %8s %8s\n' "------------------------------" -------- -------- -------- -------- -------- --------
} > "$OUT"

for m in $LIST; do
  printf '==> %s\n' "$m" >&2
  cold=$(run_once "$m")
  if [ "${cold%% *}" = "ERR" ]; then
    printf '%-30s %s\n' "$m" "$cold" >> "$OUT"; printf '    %s\n' "$cold" >&2; continue
  fi
  warm=$(run_once "$m")
  if [ "${warm%% *}" = "ERR" ]; then warm="$cold"; fi

  set -- $cold; c_api=$2
  set -- $warm; w_ttft=$1; w_api=$2; w_in=$3; w_out=$4
  line=$(python3 -c "
c_api=$c_api; w_ttft=$w_ttft; w_api=$w_api; w_in=$w_in; w_out=$w_out
print(f'{c_api/1000:8.1f} {w_api/1000:8.1f} {w_ttft/1000:8.1f} {max(0,w_api-w_ttft)/1000:8.1f} {w_in:8d} {w_out:8d}')")
  printf '%-30s %s\n' "$m" "$line" >> "$OUT"
  printf '    %s\n' "$line" >&2
done

printf '\n# Read the WARM column: it is the per-turn wait in a live session.\n' >> "$OUT"
printf '# TTFT is dominated by prefilling the system prompt, not by the model.\n' >> "$OUT"
echo "==> wrote $OUT" >&2
