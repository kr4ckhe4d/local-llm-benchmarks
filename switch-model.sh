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

# Remembers the last thing launched — either "<model> <context>" for a single
# pinned model, or "router" — so 'start' can bring it back.
STATE="$HOME/.cache/switch-model.last"

# Router mode: one process fronts every preset in models-preset.ini and loads
# them on demand, so Open WebUI's dropdown switches models with no shell at all.
# The router spawns children from /proc/self/exe, so every model runs on the
# binary the ROUTER was launched with — there is no per-model backend here, and
# that is the one thing this mode costs (gpt-oss-20b at 32k gives up Vulkan's
# 181 vs 148 tok/s). Everything else prefers ROCm anyway.
PRESET="$LLAMA_DIR/models-preset.ini"
ROUTER_BACKEND="build"   # ROCm
MODELS_MAX=1             # 16GB card — a second resident model will not allocate

# Idle sleep: after this many seconds with no requests, llama-server calls
# destroy() and releases the model — VRAM drops to ~0 while the process keeps
# listening on $PORT. The next request calls load_model() and reloads it, so
# nothing breaks, it just pays a cold start. This is what makes it safe to
# leave the server up while gaming. Set SLEEP_IDLE=-1 to disable (upstream's
# own default), or SLEEP_IDLE=<seconds> to override.
SLEEP_IDLE="${SLEEP_IDLE:-900}"

declare -A MODEL_FILE=(
  [gpt-oss-20b]="gpt-oss-20b-mxfp4.gguf"
  [qwen3.6]="Qwen3.6-35B-A3B-UD-Q4_K_M.gguf"
  [gemma4]="gemma-4-26B-A4B-it-UD-Q4_K_M.gguf"
  [qwen3-coder]="Qwen3-Coder-Next-UD-Q4_K_M.gguf"
  [muse-glimmer]="Muse-Glimmer-30B-UD-Q3_K_XL.gguf"
  [qwen3.8]="Qwen3.8-27B-UD-Q3_K_XL.gguf"
)

declare -A MODEL_LABEL=(
  [gpt-oss-20b]="GPT-OSS-20B"
  [qwen3.6]="Qwen3.6-35B-A3B"
  [gemma4]="Gemma 4-26B-A4B"
  [qwen3-coder]="Qwen3-Coder-Next"
  [muse-glimmer]="Muse Glimmer 30B"
  [qwen3.8]="Qwen3.8-27B"
)

# Which llama.cpp build to serve each model with. Measured, not guessed.
declare -A MODEL_BACKEND=(
  [gpt-oss-20b]="build-vulkan"   # MXFP4: Vulkan wins generation, 181 vs 148 tok/s
  [qwen3.6]="build"              # Q4_K_M: ROCm 2.1x pp
  [gemma4]="build"               # Q4_K_M: ROCm 1.7x pp, and wins tg too
  [qwen3-coder]="build"          # Q4_K_M: ROCm
  [muse-glimmer]="build"         # Q3_K_XL: ROCm
  [qwen3.8]="build"              # Q3_K_XL: ROCm
)

# Per-context overrides, where the winner changes with depth.
# gpt-oss at 128k: Vulkan's generation collapses to 22 tok/s at ~131k depth
# (VRAM pressure — 11.3GB model + 3GB f16 KV + compute vs 16.3GB). ROCm holds
# 70 tok/s there at the same prompt speed, so 128k goes to ROCm even though
# 32k stays on Vulkan.
declare -A BACKEND_OVERRIDE=(
  ["gpt-oss-20b:128k"]="build"
)

# Only contexts within each model's NATIVE trained range are exposed.
# Native maxima (from GGUF metadata): gpt-oss 131072, everything else 262144.
# Beyond-native configs were measured and do load — see the README — but are
# deliberately not presets, because they need YaRN and degrade output quality.
declare -A CTX_TOKENS=(
  [32k]=32768 [64k]=65536 [128k]=131072 [256k]=262144
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

  # Muse Glimmer 30B — DENSE (no -ncmoe), 52 layers, 2 KV heads (16:1 GQA) and a
  # 2048-token sliding window on 3 of every 4 layers. That attention layout is
  # why a 12.4GB dense model still fits 128K KV on a 16GB card. Native 131072.
  #
  # reasoning_strength defaults to 'high' in the chat template and will eat the
  # whole token budget before writing any content. It is a Jinja variable, not a
  # system-prompt string — only --chat-template-kwargs sets it. The JSON has no
  # spaces or glob chars, so it survives the unquoted $extra word-split intact.
  #
  # DFlash is a real 1.5GB drafter sidecar (5 blocks, block_size 16), not a
  # generic -md draft model. Measured 70.9% acceptance, mean run 3.13 tokens:
  # 52.4 vs 31.9 tok/s, a 1.64x speedup. It costs ~0.9GB VRAM, which is why it
  # is dropped at 128k — with it, VRAM sits at 15.87/15.92 GiB and any real
  # prompt OOMs.
  ["muse-glimmer:32k"]="-md models/dflash-kquant.gguf --spec-type draft-dflash -ub 512 -fa on -ctk q8_0 -ctv q8_0 --temp 1.0 --top-p 0.95 --top-k 64 --chat-template-kwargs {\"reasoning_strength\":\"low\"}"
  ["muse-glimmer:64k"]="-md models/dflash-kquant.gguf --spec-type draft-dflash -ub 256 -fa on -ctk q8_0 -ctv q8_0 --temp 1.0 --top-p 0.95 --top-k 64 --chat-template-kwargs {\"reasoning_strength\":\"low\"}"
  ["muse-glimmer:128k"]="-fa on -ctk q8_0 -ctv q8_0 --temp 1.0 --top-p 0.95 --top-k 64 --chat-template-kwargs {\"reasoning_strength\":\"low\"}"

  # Qwen3.8-27B — DENSE 27B (no -ncmoe), hybrid attention, 64 layers, 16 with
  # KV. Native 262144, but this card cannot reach it: 4 KV heads x 256 across 16
  # layers costs 34,816 B/token at q8_0, which is 2.7x Qwen3-Coder-Next. The
  # weights are 12,818 MiB and dense, so there is no expert offload to trade
  # against that — 256k needs 4,608 MiB of q4_0 KV on top and simply does not
  # fit. 128k only fits with q4_0 KV *and* -ub 256, at 281 MiB free; that margin
  # holds because the compute buffer is sized from -ub at load time and does not
  # grow with prompt length (verified: 127,116-token prompt, 5/5 needle recall,
  # no OOM). It leaves no room for a second GPU consumer, though.
  #
  # Unlike Qwen3.6, -ub barely matters here (1180 -> 1307 pp, +11% from 256 to
  # 1024) because the model is fully GPU-resident: there is no CPU-offloaded
  # weight traffic to amortise. So -ub 256 at 128k costs ~10%, not the ~3x it
  # costs Qwen3-Coder-Next.
  #
  # --reasoning-budget is not optional. reasoning_effort defaults to 'xhigh' and
  # on a hard prompt the model produces 4,684 chars of thinking and ZERO content
  # at max_tokens 1200. reasoning_effort 'low' does NOT fix it (still 0 content),
  # and on an ill-posed prompt thinking never terminates at all — 28,174 chars
  # with no </think> at max_tokens 8000. Capping the budget restores content.
  ["qwen3.8:32k"]="-ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"
  # 64k runs q8_0, not q4_0, despite the tighter fit (697 MiB free vs 1,503).
  # q4_0 KV costs up to 23% of generation at depth — measured, see README — and
  # that is the depth this preset exists for. -ub 512 buys back the compute
  # buffer q8_0 needs.
  ["qwen3.8:64k"]="-ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"
  ["qwen3.8:128k"]="-ub 256 -b 2048 -fa on -ctk q4_0 -ctv q4_0 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"
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
Usage: $(basename "$0") router            serve ALL presets, switchable from the
                                          Open WebUI dropdown (recommended)
       $(basename "$0") <model> <context>  pin one model, per-model backend
       $(basename "$0") stop      free the GPU completely (SIGTERM, then SIGKILL)
       $(basename "$0") start     relaunch whatever was running last
       $(basename "$0") status
       $(basename "$0") list

Models:
  gpt-oss-20b    GPT-OSS-20B      11.3GB  MoE 21B / 3.6B active, native 128K
                                          fastest by far (~177 tok/s, all in VRAM)
  qwen3.6        Qwen3.6-35B-A3B  20.6GB  MoE 35B / 3B active, hybrid attn (40L)
  gemma4         Gemma 4-26B-A4B  15.8GB  MoE 25.2B / 3.8B active (30L)
  qwen3-coder    Qwen3-Coder-Next 49.3GB  MoE 80B / 3B active, hybrid attn (48L)
                                          coding specialist, ~25 tok/s
  muse-glimmer   Muse Glimmer 30B 12.4GB  DENSE 30B, sliding-window attn (52L)
                                          agentic specialist, 52 tok/s with DFlash
  qwen3.8        Qwen3.8-27B      12.5GB  DENSE 27B, hybrid attn (64L), thinking
                                          32 tok/s shallow, but 9.6 at 131k depth

Context: 32k 64k 128k 256k  (only sizes within each model's native trained
range; muse-glimmer caps at 128k, gpt-oss-20b at 128k, the rest at 256k.
qwen3.8 is native 256k but VRAM-capped at 128k here — dense weights plus
4-KV-head attention leave no room. Run '$(basename "$0") list'.)

Notes:
  * 'router' vs '<model> <context>': the router serves every preset in
    models-preset.ini and loads on demand, so you switch models from the
    client instead of the shell. Its one cost is that every model runs on
    the router's own binary (ROCm), so gpt-oss-20b at 32k gives up Vulkan's
    181 vs 148 tok/s. Pin that one explicitly if you want the speed.
  * Backend is chosen per model: ROCm for K-quants, Vulkan for MXFP4.
  * Close DaVinci Resolve first — it holds ~10.4GB VRAM and will cause
    allocation failures on the tighter configs.
  * Gaming: you do not need 'stop'. After ${SLEEP_IDLE}s idle the server
    releases the model and VRAM drops to ~0 on its own, while staying up on
    port ${PORT}; the next request reloads it. Use 'stop' only to kill the
    process outright. Override with SLEEP_IDLE=<seconds>, or -1 to disable.

Examples:
  $(basename "$0") router
  $(basename "$0") qwen3-coder 256k
  $(basename "$0") gpt-oss-20b 128k
  $(basename "$0") stop
  $(basename "$0") start
  SLEEP_IDLE=-1 $(basename "$0") router            # never sleep
USAGE
}

list_combos() {
  echo "Verified model/context combinations (backend shown per context):"
  for model in gpt-oss-20b qwen3.6 gemma4 qwen3-coder muse-glimmer qwen3.8; do
    printf '  %-13s ' "$model"
    for ctx in 32k 64k 128k 256k; do
      local k="${model}:${ctx}"
      if [[ -n "${CONFIG[$k]+set}" ]]; then
        local b="${BACKEND_OVERRIDE[$k]:-${MODEL_BACKEND[$model]}}"
        [[ "$b" == "build" ]] && b="rocm" || b="vulkan"
        printf '%s[%s] ' "$ctx" "$b"
      fi
    done
    echo
  done
  echo
  echo "  rocm = build/   vulkan = build-vulkan/"
}

vram_used() {
  awk '{printf "%d", $1/1024/1024}' /sys/class/drm/card1/device/mem_info_vram_used 2>/dev/null || echo "?"
}

# SIGTERM first — llama-server shuts down cleanly on it. In router mode
# (--models-preset) this matches both the router and the child process it
# spawned per model, since both are named llama-server.
stop_server() {
  if ! pgrep -x llama-server > /dev/null 2>&1 && ! pgrep -x llama-cli > /dev/null 2>&1; then
    echo "No llama-server running. VRAM in use: $(vram_used) / 16304 MiB"
    return 0
  fi
  echo "==> Stopping llama-server/llama-cli..."
  pkill -x llama-server 2>/dev/null || true
  pkill -x llama-cli 2>/dev/null || true
  for _ in $(seq 1 10); do
    pgrep -x llama-server > /dev/null 2>&1 || pgrep -x llama-cli > /dev/null 2>&1 || break
    sleep 1
  done
  # A model mid-load can ignore SIGTERM until it finishes; escalate rather than
  # leaving the GPU pinned.
  if pgrep -x llama-server > /dev/null 2>&1 || pgrep -x llama-cli > /dev/null 2>&1; then
    echo "    still running after SIGTERM, sending SIGKILL..."
    pkill -9 -x llama-server 2>/dev/null || true
    pkill -9 -x llama-cli 2>/dev/null || true
    sleep 2
  fi
  if pgrep -x llama-server > /dev/null 2>&1 || pgrep -x llama-cli > /dev/null 2>&1; then
    echo "ERROR: a process is still running after SIGKILL." >&2
    ps -o pid,etime,cmd -C llama-server 2>/dev/null | tail -n +2 >&2 || true
    return 1
  fi
  echo "==> Stopped. VRAM in use: $(vram_used) / 16304 MiB"
}

start_router() {
  local bin="$LLAMA_DIR/$ROUTER_BACKEND/bin/llama-server"
  if [[ ! -x "$bin" ]]; then
    echo "Error: $bin not found or not executable." >&2; exit 1
  fi
  if [[ ! -f "$PRESET" ]]; then
    echo "Error: preset file $PRESET not found." >&2; exit 1
  fi

  if ! stop_server; then
    echo "ERROR: could not stop the running server, aborting." >&2
    exit 1
  fi

  echo "==> Starting router over $(basename "$PRESET")"
  echo "    backend: $ROUTER_BACKEND (applies to every model — see notes)"
  echo "    models-max: $MODELS_MAX"
  if (( SLEEP_IDLE > 0 )); then
    # Not in unset_reserved_args(), so children inherit it and each loaded model
    # releases its own VRAM after idling.
    echo "    idle sleep: ${SLEEP_IDLE}s (inherited by each spawned model)"
  fi
  mkdir -p "$(dirname "$STATE")"
  printf 'router\n' > "$STATE"
  cd "$LLAMA_DIR"
  nohup "$bin" --models-preset "$PRESET" --models-max "$MODELS_MAX" \
    --sleep-idle-seconds "$SLEEP_IDLE" \
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
    echo "ERROR: router did not become healthy in time. Check $LOG" >&2
    exit 1
  fi

  echo "==> Router live at http://192.168.4.228:${PORT} — presets available:"
  curl -s "http://localhost:${PORT}/v1/models" 2>/dev/null | python3 -c '
import json, sys
for m in json.load(sys.stdin)["data"]:
    print("     ", m["id"], "" if m.get("status", {}).get("value") != "loaded" else "[loaded]")
' 2>/dev/null || echo "     (could not list — see $LOG)"
}

start_last() {
  if [[ ! -f "$STATE" ]]; then
    echo "No previous model recorded in $STATE." >&2
    echo "Launch one explicitly first, e.g. '$(basename "$0") router'." >&2
    exit 1
  fi
  local model ctx
  read -r model ctx < "$STATE"
  if [[ "${model:-}" == "router" ]]; then
    echo "==> Restarting last config: router"
    start_router
    return
  fi
  if [[ -z "${model:-}" || -z "${ctx:-}" ]]; then
    echo "Malformed state file $STATE — expected '<model> <context>' or 'router'." >&2
    exit 1
  fi
  echo "==> Restarting last config: $model $ctx"
  switch_model "$model" "$ctx"
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
  vram=$(vram_used)
  echo "VRAM in use: ${vram} / 16304 MiB"
  # /health, /props and /v1/models all bypass the sleep state upstream, so none
  # of them report it and none of them wake the model — checking status is free.
  # Low VRAM against a live process is the observable signal.
  if [[ "$st" == "200" && "$vram" != "?" ]] && (( vram < 1500 )); then
    # Report the value the RUNNING process was launched with, not this shell's
    # $SLEEP_IDLE — they differ whenever the server was started with an override.
    local idle
    idle=$(pgrep -a -x llama-server 2>/dev/null \
             | grep -o -- '--sleep-idle-seconds [0-9-]\+' | head -1 | awk '{print $2}')
    if [[ -n "${idle:-}" ]]; then
      echo "State: sleeping (model released after ${idle}s idle; next request reloads it)"
    else
      echo "State: sleeping (model released; next request reloads it)"
    fi
  fi
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
  local backend="${BACKEND_OVERRIDE[$key]:-${MODEL_BACKEND[$model]}}"
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

  if ! stop_server; then
    echo "ERROR: could not stop the running server, aborting." >&2
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
  if (( SLEEP_IDLE > 0 )); then
    echo "    idle sleep: ${SLEEP_IDLE}s (releases VRAM, reloads on next request)"
  fi
  mkdir -p "$(dirname "$STATE")"
  printf '%s %s\n' "$model" "$ctx" > "$STATE"
  cd "$LLAMA_DIR"
  # shellcheck disable=SC2086
  nohup "$bin" -m "models/$file" -ngl 99 -c "$tokens" $extra -np 1 \
    --sleep-idle-seconds "$SLEEP_IDLE" \
    --host "$HOST" --port "$PORT" > "$LOG" 2>&1 < /dev/null &
  disown

  echo "==> Waiting for health check..."
  local ok=0 st
  # Qwen3-Coder-Next is 49GB and can take a couple of minutes to load cold.
  for _ in $(seq 1 80); do
    # DFlash always emits "[spec] failed to measure draft model memory: failed
    # to create llama_context" during its memory-fitting probe, and the log
    # itself calls that normal. Filter it out or every muse-glimmer launch
    # aborts on a healthy server.
    if grep -i 'failed to \(allocate\|create\)' "$LOG" 2>/dev/null \
         | grep -qv '\[spec\] failed to measure'; then
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
  stop) stop_server ;;
  start) start_last ;;
  router) start_router ;;
  *)
    if [[ $# -lt 2 ]]; then usage; exit 1; fi
    switch_model "$1" "$2"
    ;;
esac
