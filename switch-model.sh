#!/usr/bin/env bash
# Switch which local model llama-server is serving, using the configs verified
# by benchmarking in ~/code/local-llm-benchmarks/. One process holds one model
# at a time — this always does a full stop/start, there is no hot-swap.
# See that repo's README for the raw numbers behind every config below.
set -euo pipefail

LLAMA_DIR="$HOME/llama.cpp"
# ROCm/HIP build — ~2x faster than build-vulkan/ on this GPU (gfx1201).
# Do not switch this back to build-vulkan/ without re-verifying every -ncmoe
# below: Gemma 4's Vulkan values do NOT load on ROCm and vice versa.
BIN="$LLAMA_DIR/build/bin/llama-server"
MODEL_DIR="$LLAMA_DIR/models"
LOG="/tmp/llama-server.log"
PORT=8090
HOST="0.0.0.0"

declare -A MODEL_FILE=(
  [gpt-oss-20b]="gpt-oss-20b-mxfp4.gguf"
  [qwen3.6]="Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"
  [gemma4]="gemma-4-26B-A4B-it-UD-Q4_K_M.gguf"
  [qwen3-coder]="Qwen3-Coder-Next-UD-Q4_K_M.gguf"
)

declare -A MODEL_LABEL=(
  [gpt-oss-20b]="GPT-OSS-20B"
  [qwen3.6]="Qwen3.6-35B-A3B"
  [gemma4]="Gemma 4-26B-A4B"
  [qwen3-coder]="Qwen3-Coder-Next"
)

declare -A CTX_TOKENS=(
  [4k]=4096 [32k]=32768 [128k]=131072
  [256k]=262144 [512k]=524288 [1m]=1048576
)

# key "<model>:<ctx>" -> extra llama-server flags beyond "-ngl 99 -c <tokens>".
# Every value here was actually loaded on the ROCm build and confirmed to reach
# "server is listening" with real headroom left over — not the absolute
# tightest -ncmoe found. Combos not listed were either not tested or exceed
# that model's supported context.
declare -A CONFIG=(
  # GPT-OSS-20B — Vulkan-era values, re-verified as still loading on ROCm.
  ["gpt-oss-20b:4k"]=""
  ["gpt-oss-20b:32k"]=""
  ["gpt-oss-20b:128k"]=""
  ["gpt-oss-20b:256k"]="-fa on -ctk q8_0 -ctv q8_0"
  ["gpt-oss-20b:512k"]="-ncmoe 9 -fa on -ctk q8_0 -ctv q8_0"
  ["gpt-oss-20b:1m"]="-ncmoe 24 -fa on -ctk q4_0 -ctv q4_0"

  # Qwen3.6-35B-A3B — hybrid attention, 40 layers, 10 with KV.
  ["qwen3.6:4k"]="-ncmoe 16 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3.6:32k"]="-ncmoe 16 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3.6:128k"]="-ncmoe 20 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3.6:256k"]="-ncmoe 24 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3.6:512k"]="-ncmoe 32 -ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3.6:1m"]="-ncmoe 40 -ub 256 -b 1024 -fa on -ctk q8_0 -ctv q8_0"

  # Gemma 4 — RE-TUNED for ROCm. The old Vulkan values (3/5/8/16) do not load.
  # Not a hybrid-attention model; hard-caps at 256K.
  ["gemma4:4k"]="-ncmoe 6"
  ["gemma4:32k"]="-ncmoe 8"
  ["gemma4:128k"]="-ncmoe 12"
  ["gemma4:256k"]="-ncmoe 20"

  # Qwen3-Coder-Next — hybrid attention, 48 layers, 12 with KV. ~47GB host RAM.
  # 1M requires q4_0 KV: q8_0 KV is 13,056 MiB and the compute buffer then
  # overflows 16,304 MiB.
  ["qwen3-coder:4k"]="-ncmoe 38 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3-coder:32k"]="-ncmoe 38 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3-coder:128k"]="-ncmoe 40 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3-coder:256k"]="-ncmoe 42 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3-coder:1m"]="-ncmoe 46 -ub 256 -b 1024 -fa on -ctk q4_0 -ctv q4_0"
)

# Contexts beyond a model's native 262144 need YaRN for output quality.
# Applied automatically for the 1m preset on the two Qwen models.
declare -A YARN=(
  [qwen3.6]="--rope-scaling yarn --rope-scale 4 --yarn-orig-ctx 262144"
  [qwen3-coder]="--rope-scaling yarn --rope-scale 4 --yarn-orig-ctx 262144"
)

usage() {
  cat <<USAGE
Usage: $(basename "$0") <model> <context>
       $(basename "$0") status
       $(basename "$0") list

Models:
  gpt-oss-20b    GPT-OSS-20B      11.3GB  MoE 21B total / 3.6B active
  qwen3.6        Qwen3.6-35B-A3B  20.6GB  MoE 35B / 3B active, hybrid attn (40L)
  gemma4         Gemma 4-26B-A4B  15.8GB  MoE 25.2B / 3.8B active (30L, max 256K)
  qwen3-coder    Qwen3-Coder-Next 49.3GB  MoE 80B / 3B active, hybrid attn (48L)
                                          coding specialist — best 1M option

Context: 4k 32k 128k 256k 512k 1m  (not every model supports every size —
run '$(basename "$0") list' to see the verified combinations)

Notes:
  * Uses the ROCm build (build/), ~2x faster than Vulkan on this GPU.
  * Close DaVinci Resolve first — it holds ~10.4GB VRAM and will cause
    allocation failures on the tighter configs.

Examples:
  $(basename "$0") qwen3-coder 1m
  $(basename "$0") qwen3.6 256k
  $(basename "$0") status
USAGE
}

list_combos() {
  echo "Verified model/context combinations (ROCm build):"
  for model in gpt-oss-20b qwen3.6 gemma4 qwen3-coder; do
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
  if ! pgrep -x llama-server > /dev/null 2>&1; then
    echo "No llama-server running."
    return 0
  fi
  echo "llama-server is running:"
  ps -o pid,etime,cmd -C llama-server 2>/dev/null | tail -n +2 || true
  echo
  local st
  st=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${PORT}/health" 2>/dev/null || echo "000")
  echo "Health: $st"
  local vram
  vram=$(awk '{printf "%d", $1/1024/1024}' /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null || echo "?")
  echo "VRAM in use: ${vram} / 16304 MiB"
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
    echo "Error: ${MODEL_LABEL[$model]} was never verified at ${ctx}" >&2
    echo "(either untested, or beyond that model's supported context range)." >&2
    echo "Run '$(basename "$0") list' to see what's actually been verified." >&2
    exit 1
  fi

  local extra="${CONFIG[$key]}"
  local tokens="${CTX_TOKENS[$ctx]}"
  local file="${MODEL_FILE[$model]}"

  # Past 262144 the model is out of its trained range without RoPE scaling.
  if (( tokens > 262144 )) && [[ -n "${YARN[$model]:-}" ]]; then
    extra="$extra ${YARN[$model]}"
  fi

  if [[ ! -f "$MODEL_DIR/$file" ]]; then
    echo "Error: $MODEL_DIR/$file not found." >&2
    exit 1
  fi

  echo "==> Stopping any running llama-server/llama-cli..."
  pkill -x llama-server 2>/dev/null || true
  pkill -x llama-cli 2>/dev/null || true
  sleep 2
  if pgrep -x llama-server > /dev/null 2>&1 || pgrep -x llama-cli > /dev/null 2>&1; then
    echo "ERROR: a process is still running after kill, aborting." >&2
    exit 1
  fi

  # A big VRAM consumer (Resolve, a game, a compositor doing something odd)
  # is the usual cause of an allocation failure on a config that used to work.
  local vram_before
  vram_before=$(awk '{printf "%d", $1/1024/1024}' /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null || echo 0)
  if (( vram_before > 1500 )); then
    echo "    WARNING: ${vram_before} MiB of VRAM already in use before load."
    echo "    If this fails to allocate, close whatever is holding it (DaVinci"
    echo "    Resolve holds ~10.4GB) and retry."
  fi

  echo "==> Starting ${MODEL_LABEL[$model]} @ ${ctx} (${tokens} tokens)"
  echo "    flags: -ngl 99 -c $tokens $extra"
  cd "$LLAMA_DIR"
  # shellcheck disable=SC2086
  nohup "$BIN" -m "models/$file" -ngl 99 -c "$tokens" $extra -np 1 \
    --host "$HOST" --port "$PORT" > "$LOG" 2>&1 < /dev/null &
  disown

  echo "==> Waiting for health check..."
  local ok=0 st
  # Qwen3-Coder-Next is 49GB and can take a couple of minutes to load cold.
  for _ in $(seq 1 80); do
    if grep -qi 'failed to \(allocate\|create\)' "$LOG" 2>/dev/null; then
      echo "ERROR: allocation failed. Last lines of $LOG:" >&2
      grep -iE 'allocating|failed' "$LOG" | tail -5 >&2
      exit 1
    fi
    st=$(curl -s -o /dev/null -w '%{http_code}' "http://localhost:${PORT}/health" 2>/dev/null || echo "000")
    if [[ "$st" == "200" ]]; then ok=1; break; fi
    sleep 3
  done
  if [[ "$ok" -ne 1 ]]; then
    echo "ERROR: server did not become healthy in time. Check $LOG" >&2
    exit 1
  fi

  local vram_after
  vram_after=$(awk '{printf "%d", $1/1024/1024}' /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null || echo "?")
  echo "==> Loaded. VRAM: ${vram_after} / 16304 MiB"
  grep -iE 'kv_cache: size|recurrent: size' "$LOG" | tail -2 || true

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
