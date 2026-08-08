#!/usr/bin/env bash
# Switch which local model llama-server is serving, using the configs verified
# by benchmarking in ~/code/local-llm-benchmarks/. One process holds one model
# at a time — this always does a full stop/start, there is no hot-swap.
# See that repo's README for the raw numbers behind every config below.
set -euo pipefail

LLAMA_DIR="$HOME/llama.cpp"
# Backend is PER-MODEL — there is no single best build on this GPU:
#   K-quants (Q4_K_M):  ROCm wins prompt processing by 1.7-2.1x, generation ties.
#   MXFP4 (gpt-oss):    Vulkan wins BOTH (pp 3760 vs 2692, tg 177 vs 139).
# The -ncmoe values below are backend-specific — Gemma 4's Vulkan values do not
# load on ROCm. Do not change a model's backend without re-verifying its configs.
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

# Which llama.cpp build to serve each model with. See the note at the top —
# measured per model, not guessed.
declare -A MODEL_BACKEND=(
  [gpt-oss-20b]="build-vulkan"   # MXFP4: Vulkan is 40% faster pp, 27% faster tg
  [qwen3.6]="build"              # Q4_K_M: ROCm 2.1x pp
  [gemma4]="build"               # Q4_K_M: ROCm 1.7x pp
  [qwen3-coder]="build"          # Q4_K_M: ROCm
)

# Only contexts within each model's NATIVE trained range are exposed.
# Native maxima (from GGUF metadata): gpt-oss 131072, everything else 262144.
# Beyond-native configs were measured and do load — see the README — but are
# deliberately not presets, because they need YaRN and degrade output quality.
declare -A CTX_TOKENS=(
  [32k]=32768 [128k]=131072 [256k]=262144
)

# key "<model>:<ctx>" -> extra llama-server flags beyond "-ngl 99 -c <tokens>".
# Every value here was actually loaded on the ROCm build and confirmed to reach
# "server is listening" with real headroom left over — not the absolute
# tightest -ncmoe found. Combos not listed were either not tested or exceed
# that model's supported context.
declare -A CONFIG=(
  # GPT-OSS-20B — native 131072, and that is already YaRN-stretched 32x from a
  # 4096 base (see gpt-oss.rope.scaling.* in the GGUF). 128k is its ceiling.
  ["gpt-oss-20b:32k"]=""
  ["gpt-oss-20b:128k"]=""

  # Qwen3.6-35B-A3B — hybrid attention, 40 layers, 10 with KV. Native 262144.
  ["qwen3.6:32k"]="-ncmoe 16 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3.6:128k"]="-ncmoe 20 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3.6:256k"]="-ncmoe 24 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"

  # Gemma 4 — RE-TUNED for ROCm. The old Vulkan values (5/8/16) do not load.
  # Not a hybrid-attention model. Native 262144.
  ["gemma4:32k"]="-ncmoe 8"
  ["gemma4:128k"]="-ncmoe 12"
  ["gemma4:256k"]="-ncmoe 20"

  # Qwen3-Coder-Next — hybrid attention, 48 layers, 12 with KV. Native 262144.
  # ~47GB host RAM at these settings.
  ["qwen3-coder:32k"]="-ncmoe 38 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3-coder:128k"]="-ncmoe 40 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
  ["qwen3-coder:256k"]="-ncmoe 42 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0"
)

# Kept as a guard, not currently reachable: every preset above is within its
# model's native range. If a beyond-native context is ever re-added to
# CTX_TOKENS/CONFIG, this ensures it gets RoPE scaling rather than silently
# running out of trained range and emitting garbage.
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
  gpt-oss-20b    GPT-OSS-20B      11.3GB  MoE 21B / 3.6B active, native 128K
                                          fastest by far (~177 tok/s, all in VRAM)
  qwen3.6        Qwen3.6-35B-A3B  20.6GB  MoE 35B / 3B active, hybrid attn (40L)
  gemma4         Gemma 4-26B-A4B  15.8GB  MoE 25.2B / 3.8B active (30L)
  qwen3-coder    Qwen3-Coder-Next 49.3GB  MoE 80B / 3B active, hybrid attn (48L)
                                          coding specialist, ~25 tok/s

Context: 32k 128k 256k  (only sizes within each model's native trained range;
gpt-oss-20b caps at 128k, the rest at 256k. Run '$(basename "$0") list'.)

Notes:
  * Backend is chosen per model: ROCm for K-quants, Vulkan for MXFP4.
  * Close DaVinci Resolve first — it holds ~10.4GB VRAM and will cause
    allocation failures on the tighter configs.

Examples:
  $(basename "$0") qwen3-coder 256k
  $(basename "$0") gpt-oss-20b 128k
  $(basename "$0") status
USAGE
}

list_combos() {
  echo "Verified model/context combinations:"
  for model in gpt-oss-20b qwen3.6 gemma4 qwen3-coder; do
    printf '  %-13s [%-12s] ' "$model" "${MODEL_BACKEND[$model]}"
    for ctx in 32k 128k 256k; do
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
  local backend="${MODEL_BACKEND[$model]}"
  local bin="$LLAMA_DIR/$backend/bin/llama-server"

  if [[ ! -x "$bin" ]]; then
    echo "Error: $bin not found or not executable." >&2
    exit 1
  fi

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
  echo "    backend: $backend"
  echo "    flags: -ngl 99 -c $tokens $extra"
  cd "$LLAMA_DIR"
  # shellcheck disable=SC2086
  nohup "$bin" -m "models/$file" -ngl 99 -c "$tokens" $extra -np 1 \
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
