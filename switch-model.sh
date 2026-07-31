#!/usr/bin/env bash
# Switch which local model llama-server is serving, using the configs found
# by benchmarking in ~/code/gemma-test/local-llm-benchmarks/ on the Mac side.
# One process holds one model at a time — this always does a full stop/start,
# there is no hot-swap. See that repo's README for the raw numbers behind
# every config below.
set -euo pipefail

LLAMA_DIR="$HOME/llama.cpp"
BIN="$LLAMA_DIR/build-vulkan/bin/llama-server"
MODEL_DIR="$LLAMA_DIR/models"
LOG="/tmp/llama-server.log"
PORT=8090
HOST="0.0.0.0"

declare -A MODEL_FILE=(
  [gpt-oss-20b]="gpt-oss-20b-mxfp4.gguf"
  [gpt-oss-120b]="gpt-oss-120b-mxfp4.gguf"   # deleted from disk, kept for reference
  [qwen3.6]="Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"
  [gemma4]="gemma-4-26B-A4B-it-UD-Q4_K_M.gguf"
  [qwen3-coder]="Qwen3-Coder-Next-UD-Q4_K_M.gguf"
)

declare -A MODEL_LABEL=(
  [gpt-oss-20b]="GPT-OSS-20B"
  [gpt-oss-120b]="GPT-OSS-120B"
  [qwen3.6]="Qwen3.6-35B-A3B"
  [gemma4]="Gemma 4-26B-A4B"
  [qwen3-coder]="Qwen3-Coder-Next"
)

declare -A CTX_TOKENS=(
  [4k]=4096 [32k]=32768 [128k]=131072
  [256k]=262144 [512k]=524288 [1m]=1010000
)

# key "<model>:<ctx>" -> extra llama-server flags beyond "-ngl 99 -c <tokens>".
# Every value here is a config that was actually run and confirmed to fit
# with real headroom (not the absolute tightest -ncmoe found, which several
# tests showed leaves near-zero margin for real traffic). Combos not listed
# were either not tested or exceed that model's supported context.
declare -A CONFIG=(
  ["gpt-oss-20b:4k"]=""
  ["gpt-oss-20b:32k"]=""
  ["gpt-oss-20b:128k"]=""
  ["gpt-oss-20b:256k"]="-fa on -ctk q8_0 -ctv q8_0"
  ["gpt-oss-20b:512k"]="-ncmoe 9 -fa on -ctk q8_0 -ctv q8_0"
  ["gpt-oss-20b:1m"]="-ncmoe 24 -fa on -ctk q4_0 -ctv q4_0"

  ["gpt-oss-120b:4k"]="-ncmoe 28"
  ["gpt-oss-120b:32k"]="-ncmoe 29"
  ["gpt-oss-120b:128k"]="-ncmoe 31"

  ["qwen3.6:4k"]="-ncmoe 12"
  ["qwen3.6:32k"]="-ncmoe 14"
  ["qwen3.6:128k"]="-ncmoe 18"
  ["qwen3.6:256k"]="-ncmoe 18 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3.6:512k"]="-ncmoe 25 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3.6:1m"]="-ncmoe 42 -fa on -ctk q8_0 -ctv q8_0"

  ["gemma4:4k"]="-ncmoe 3"
  ["gemma4:32k"]="-ncmoe 5"
  ["gemma4:128k"]="-ncmoe 8"
  ["gemma4:256k"]="-ncmoe 16"

  ["qwen3-coder:4k"]="-ncmoe 35"
  ["qwen3-coder:32k"]="-ncmoe 35"
)

usage() {
  cat <<USAGE
Usage: $(basename "$0") <model> <context>
       $(basename "$0") status
       $(basename "$0") list

Models:
  gpt-oss-20b    GPT-OSS-20B      11.3GB  MoE 21B total / 3.6B active
  gpt-oss-120b   GPT-OSS-120B     59.0GB  MoE 117B total / 5.1B active (deleted from disk)
  qwen3.6        Qwen3.6-35B-A3B  20.6GB  MoE 35B total / 3B active
  gemma4         Gemma 4-26B-A4B  15.8GB  MoE 25.2B total / 3.8B active (30 layers)
  qwen3-coder    Qwen3-Coder-Next 49.3GB  MoE 80B total / 3B active (48 layers, coding specialist)

Context: 4k 32k 128k 256k 512k 1m  (not every model supports every size —
run '$(basename "$0") list' to see the tested combinations)

Examples:
  $(basename "$0") gpt-oss-20b 128k
  $(basename "$0") qwen3.6 1m
  $(basename "$0") status
USAGE
}

list_combos() {
  echo "Tested model/context combinations:"
  for model in gpt-oss-20b gpt-oss-120b qwen3.6 gemma4 qwen3-coder; do
    printf '  %-13s ' "$model"
    for ctx in 4k 32k 128k 256k 512k 1m; do
      if [[ -n "${CONFIG[${model}:${ctx}]+set}" ]]; then
        printf '%s ' "$ctx"
      fi
    done
    echo
  done
}

status() {
  if ! pgrep -f 'llama-server' > /dev/null 2>&1; then
    echo "No llama-server running."
    return 0
  fi
  echo "llama-server is running:"
  ps -o pid,etime,cmd -C llama-server 2>/dev/null | tail -n +2 || \
    pgrep -af llama-server
  echo
  local st
  st=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${PORT}/health" 2>/dev/null || echo "000")
  echo "Health: $st"
  if [[ "$st" == "200" ]]; then
    curl -s "http://localhost:${PORT}/v1/models" 2>/dev/null | python3 -m json.tool 2>/dev/null || true
  fi
}

switch_model() {
  local model="$1" ctx="$2"

  if [[ -z "${MODEL_FILE[$model]:-}" ]]; then
    echo "Unknown model: $model" >&2; usage; exit 1
  fi
  if [[ -z "${CTX_TOKENS[$ctx]:-}" ]]; then
    echo "Unknown context: $ctx" >&2; usage; exit 1
  fi

  local key="${model}:${ctx}"
  if [[ -z "${CONFIG[$key]+set}" ]]; then
    echo "Error: ${MODEL_LABEL[$model]} was never benchmarked at ${ctx}" >&2
    echo "(either untested, or beyond that model's supported context range)." >&2
    echo "Run '$(basename "$0") list' to see what's actually been tested." >&2
    exit 1
  fi

  local extra="${CONFIG[$key]}"
  local tokens="${CTX_TOKENS[$ctx]}"
  local file="${MODEL_FILE[$model]}"

  if [[ ! -f "$MODEL_DIR/$file" ]]; then
    echo "Error: $MODEL_DIR/$file not found." >&2
    exit 1
  fi

  echo "==> Stopping any running llama-server/llama-cli..."
  pkill -f 'llama-server|llama-cli' 2>/dev/null || true
  sleep 2
  if pgrep -f 'llama-server|llama-cli' > /dev/null 2>&1; then
    echo "ERROR: a process is still running after kill, aborting." >&2
    exit 1
  fi

  echo "==> Starting ${MODEL_LABEL[$model]} @ ${ctx} (${tokens} tokens)"
  [[ -n "$extra" ]] && echo "    flags: -ngl 99 -c $tokens $extra"
  cd "$LLAMA_DIR"
  # shellcheck disable=SC2086
  nohup "$BIN" -m "models/$file" -ngl 99 -c "$tokens" $extra -np 1 \
    --host "$HOST" --port "$PORT" > "$LOG" 2>&1 < /dev/null &
  disown

  echo "==> Waiting for health check..."
  local ok=0 st
  for _ in $(seq 1 40); do
    st=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${PORT}/health" 2>/dev/null || echo "000")
    if [[ "$st" == "200" ]]; then ok=1; break; fi
    sleep 3
  done
  if [[ "$ok" -ne 1 ]]; then
    echo "ERROR: server did not become healthy in time. Check $LOG" >&2
    exit 1
  fi

  echo "==> Loaded. Memory breakdown:"
  grep -A3 'memory breakdown' "$LOG" | tail -3 || true

  echo "==> Test request:"
  curl -s "http://localhost:${PORT}/v1/chat/completions" -H 'Content-Type: application/json' \
    -d '{"messages":[{"role":"user","content":"Say hi in three words."}],"max_tokens":20}' \
    | python3 -c '
import json, sys
d = json.load(sys.stdin)
m = d["choices"][0]["message"]
print(m.get("content") or m.get("reasoning_content", "")[:100])
' 2>/dev/null || echo "  (request sent — see $LOG if this looks wrong)"

  echo "==> ${MODEL_LABEL[$model]} is live at http://192.168.4.228:${PORT}"
}

case "${1:-}" in
  ""|-h|--help) usage ;;
  status) status ;;
  list) list_combos ;;
  *)
    if [[ $# -lt 2 ]]; then usage; exit 1; fi
    switch_model "$1" "$2"
    ;;
esac
