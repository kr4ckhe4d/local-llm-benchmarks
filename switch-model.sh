#!/usr/bin/env bash
# Switch which local model llama-server is serving, using the configs verified
# by benchmarking in ~/code/local-llm-benchmarks/. One process holds one model
# at a time — this always does a full stop/start, there is no hot-swap.
# See that repo's README for the raw numbers behind every config below.
set -euo pipefail

# This script drives the GPUs on the Linux box, so refuse anywhere else. The
# tables below need bash 4+ (declare -A); macOS ships bash 3.2, where the first
# one dies as "gpt: unbound variable". The /sys check also catches a Mac with a
# newer bash from Homebrew.
if (( BASH_VERSINFO[0] < 4 )) || [[ ! -d /sys/class/drm ]]; then
  echo "switch-model.sh runs on the GPU box (needs bash 4+ and /sys/class/drm)." >&2
  echo "From another machine: ssh <gpu-box> switch-model ${*:-router}" >&2
  exit 2
fi

LLAMA_DIR="$HOME/llama.cpp"
# Single backend: build/ (ROCm). Vulkan was retired — its only win was shallow
# MXFP4 generation for gpt-oss-20b (181 vs 148 tok/s), which applied solely to
# the pinned 32k case. Router mode always ran ROCm, ROCm wins prompt outright,
# and it wins 128k by 3.2x. The -ncmoe values below are ROCm-specific; Gemma 4's
# old Vulkan values do not load here.
MODEL_DIR="$LLAMA_DIR/models"
LOG="/tmp/llama-server.log"
PORT=8090
HOST="0.0.0.0"

# Remembers the last thing launched — either "<model> <context>" for a single
# pinned model, or "router" — so 'start' can bring it back.
STATE="$HOME/.cache/switch-model.last"

# VRAM readings across every dGPU, added 2026-10-05 with the R9700. This used to
# read card1 only, which with two cards is a fraction of a split model. The
# script is reached through two symlinks (~/.local/bin, ~/llama.cpp), so resolve
# the real path before looking for the helper next to it.
. "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/benchmarks/gpu-mem.sh"

# Router mode: one process fronts every preset in models-preset.ini and loads
# them on demand, so Open WebUI's dropdown switches models with no shell at all.
# The router spawns children from /proc/self/exe, so every model runs on the
# binary the ROUTER was launched with. That used to cost gpt-oss-20b its Vulkan
# generation advantage at 32k; now that Vulkan is retired there is no per-model
# backend at all, so router and pinned mode are equivalent on that axis.
PRESET="$LLAMA_DIR/models-preset.ini"
ROUTER_BACKEND="build"   # ROCm
MODELS_MAX=1             # MoE presets take 19-43 GB of the 48.9 across both cards

# Idle sleep: after this many seconds with no requests, llama-server calls
# destroy() and releases the model — VRAM drops to ~0 while the process keeps
# listening on $PORT. The next request calls load_model() and reloads it, so
# nothing breaks, it just pays a cold start. This is what makes it safe to
# leave the server up while gaming. Set SLEEP_IDLE=-1 to disable (upstream's
# own default), or SLEEP_IDLE=<seconds> to override.
SLEEP_IDLE="${SLEEP_IDLE:-900}"

declare -A MODEL_FILE=(
  [qwen3.8]="Qwen3.8-27B-UD-Q6_K.gguf"
  [qwen3.8-mtp]="Qwen3.8-27B-UD-Q6_K.gguf"   # kept for old commands; = qwen3.8
  [qwen3.8-q8]="Qwen3.8-27B-Q8_0.gguf"
  [qwen3.5-uncensored]="Qwen3.5-27B-Uncensored-Q3_K_M.gguf"
  [qwen3.5-9b-uncensored]="Qwen3.5-9B-Uncensored-Q8_0.gguf"
  [gemma4-12b]="gemma-4-12B-it-Q8_0.gguf"
)

declare -A MODEL_LABEL=(
  [qwen3.8]="Qwen3.8-27B"
  [qwen3.8-mtp]="Qwen3.8-27B +MTP"
  [qwen3.8-q8]="Qwen3.8-27B Q8_0 +MTP"
  [qwen3.5-uncensored]="Qwen3.5-27B-Uncensored"
  [qwen3.5-9b-uncensored]="Qwen3.5-9B-Uncensored"
  [gemma4-12b]="Gemma 4-12B Q8_0 +vision +MTP"
)

# Which llama.cpp build to serve each model with. Measured, not guessed.
declare -A MODEL_BACKEND=(
  [qwen3.8]="build"              # UD-Q6_K + MTP since 2026-10-07: ROCm
  [qwen3.8-mtp]="build"          # UD-Q6_K + MTP since 2026-10-07: ROCm
  [qwen3.8-q8]="build"           # Q8_0 + MTP: ROCm
  [qwen3.5-uncensored]="build"   # Q3_K_M: ROCm
  [qwen3.5-9b-uncensored]="build" # Q8_0: ROCm
  [gemma4-12b]="build"           # Q8_0 + mmproj + MTP: ROCm
)

# Kept as a hook, now empty. Every model runs on build/ (ROCm) — the Vulkan
# build was retired once gpt-oss-20b moved across, since nothing else used it.
# Its one advantage was shallow generation on MXFP4 (181 vs 148 tok/s), which
# only applied to the pinned 32k case; router mode always ran ROCm anyway, and
# ROCm wins prompt outright and wins 128k by 3.2x (70.5 vs 22.3).
declare -A BACKEND_OVERRIDE=()

# Only contexts within each model's NATIVE trained range are exposed.
# Native maxima (from GGUF metadata): gpt-oss 131072, everything else 262144.
# Beyond-native configs were measured and do load — see the README — but are
# deliberately not presets, because they need YaRN and degrade output quality.
# The 512k and 1m labels are kept for any future model that reaches them
# natively; none currently on disk does.
declare -A CTX_TOKENS=(
  [16k]=16384 [32k]=32768 [64k]=65536 [128k]=131072 [256k]=262144
  [512k]=524288 [1m]=1048576
  # 202752 was GLM-4.7-Flash's native ceiling (removed 2026-10-07); the bucket
  # stays for any future model with the same odd maximum.
  [200k]=202752
)

# key "<model>:<ctx>" -> extra llama-server flags beyond "-ngl 99 -c <tokens>".
# Every value here was actually loaded on the ROCm build and confirmed to reach
# "server is listening" with real headroom left over — not the absolute
# tightest -ncmoe found. Combos not listed were either not tested or exceed
# that model's supported context.
# TWO CARDS since 2026-10-05 (9070 XT + R9700, 48.9 GB, auto layer split).
# -ncmoe is gone from every MoE config below: the
# experts now fit in VRAM, which is worth +40% to +185% generation. Comments
# below that explain a particular -ncmoe value, or a feature dropped "for
# VRAM", describe the single 16 GB card. models-preset.ini holds the measured
# before/after for each config and is the reference; this table mirrors it.
declare -A CONFIG=(
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
  # TWO CARDS (2026-10-05): every Qwen3.8 config is IQ4_XS-v3 + q8_0 KV + MTP.
  # On 16 GB, MTP was confined to 16k/32k on Q3_K_XL with q4_0 KV, and 128k ran
  # q4_0 without it. Now 71 tok/s shallow at any context, 27 at 128K depth (was
  # 9.2). -ub 512 from 128k up: it beats 1024 by 15% prefill at depth. 16k is
  # gone; it existed only because MTP fit nowhere larger. See models-preset.ini.
  ["qwen3.8:32k"]="--chat-template-file /home/nipuna/code/local-llm-benchmarks/templates/qwen38-late-system.jinja -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"
  ["qwen3.8:64k"]="--chat-template-file /home/nipuna/code/local-llm-benchmarks/templates/qwen38-late-system.jinja -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"
  ["qwen3.8:128k"]="--chat-template-file /home/nipuna/code/local-llm-benchmarks/templates/qwen38-late-system.jinja -ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"
  ["qwen3.8:256k"]="--chat-template-file /home/nipuna/code/local-llm-benchmarks/templates/qwen38-late-system.jinja -ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"

  # qwen3.8-mtp is the same model and flags now; kept so old commands work.
  ["qwen3.8-mtp:32k"]="--chat-template-file /home/nipuna/code/local-llm-benchmarks/templates/qwen38-late-system.jinja -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"

  # Q8_0 + MTP: near-lossless, 50 tok/s. 256k leaves 933 MiB on the 9070 XT.
  ["qwen3.8-q8:32k"]="--chat-template-file /home/nipuna/code/local-llm-benchmarks/templates/qwen38-late-system.jinja -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"
  ["qwen3.8-q8:128k"]="--chat-template-file /home/nipuna/code/local-llm-benchmarks/templates/qwen38-late-system.jinja -ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"

  # Qwen3.5-27B-Uncensored (HauhauCS, Aggressive) — DENSE 27B, arch qwen35, the
  # same architecture as qwen3.8 above one base version back. Same rules: no
  # -ncmoe, native 262144 unreachable.
  #
  # It measures 266 MiB heavier than qwen3.8 at 64k, and that difference is
  # decisive: q8_0 at 64k leaves 55 MiB, which is smaller than the range the
  # desktop's own VRAM moved during a single measuring session (395-701 MiB).
  # So 64k here takes q4_0 and eats the ~23% generation penalty that qwen3.8's
  # 64k preset specifically exists to avoid. At 32k the gap is only 67 MiB and
  # q8_0 is comfortable at 1,127 MiB free — 32k is the preset to reach for.
  #
  # (Single card.) No 128k: it loaded at 32 MiB free, below the drift above. On
  # two cards 128k leaves 8,979 MiB on the 9070 XT and is a preset again, and
  # 64k is back on q8_0 KV.
  ["qwen3.5-uncensored:32k"]="--chat-template-file /home/nipuna/code/local-llm-benchmarks/templates/qwen35-late-system.jinja -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"
  ["qwen3.5-uncensored:64k"]="--chat-template-file /home/nipuna/code/local-llm-benchmarks/templates/qwen35-late-system.jinja -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"
  ["qwen3.5-uncensored:128k"]="--chat-template-file /home/nipuna/code/local-llm-benchmarks/templates/qwen35-late-system.jinja -ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"

  # Qwen3.5-9B-Uncensored (HauhauCS, Aggressive) — DENSE 9B, arch qwen35, same
  # family as qwen3.5-uncensored above but 32 layers not 64: half the
  # layers-with-KV (8 vs 16), same 4 KV heads, so half the per-token KV cost.
  # That is why this is the first DENSE model on this card to reach native
  # 262144 at full q8_0 precision with real headroom (1,304 MiB free at 256k) —
  # every other native-256k model here is MoE, and every other dense
  # hybrid-attention model here (qwen3.8, qwen3.5-uncensored) is VRAM-capped
  # well short of native. -ub 1024 and q8_0 KV hold at every context; there was
  # never a tradeoff to make. Pinned to the R9700 (-dev ROCm1) since
  # 2026-10-06, like gpt-oss-20b: the split cost 4% (55.4 vs 57.8 tok/s).
  ["qwen3.5-9b-uncensored:32k"]="--chat-template-file /home/nipuna/code/local-llm-benchmarks/templates/qwen35-late-system.jinja -dev ROCm1 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"
  ["qwen3.5-9b-uncensored:128k"]="--chat-template-file /home/nipuna/code/local-llm-benchmarks/templates/qwen35-late-system.jinja -dev ROCm1 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"
  ["qwen3.5-9b-uncensored:256k"]="--chat-template-file /home/nipuna/code/local-llm-benchmarks/templates/qwen35-late-system.jinja -dev ROCm1 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 --reasoning-budget 1024"

  # Gemma 4-12B — DENSE 12B, multimodal (image + experimental audio through the
  # mmproj), native 262144. MTP drafter is a separate file, so it needs -md as
  # well as --spec-type. Pinned to the R9700: 18.0 GB at 128k, 19.4 GB at 256k.
  # 101-114 tok/s with MTP (2026-10-28). Mirrors gemma4-12B-q8-vision-256k.
  ["gemma4-12b:128k"]="--mmproj models/mmproj-gemma-4-12B-it-BF16.gguf -md models/mtp-gemma-4-12B-it-Q8_0.gguf --spec-type draft-mtp -dev ROCm1 --reasoning-budget 1024 --repeat-penalty 1.05"
  ["gemma4-12b:256k"]="--mmproj models/mmproj-gemma-4-12B-it-BF16.gguf -md models/mtp-gemma-4-12B-it-Q8_0.gguf --spec-type draft-mtp -dev ROCm1 --reasoning-budget 1024 --repeat-penalty 1.05"



)

# Kept as a guard, not currently reachable: every preset above is within its
# model's native range. If a beyond-native context is ever re-added to
# CTX_TOKENS/CONFIG, this ensures it gets RoPE scaling rather than silently
# running out of trained range and emitting garbage.
declare -A YARN=()

usage() {
  cat <<USAGE
Usage: $(basename "$0") router [nothink]  serve ALL presets, switchable from the
                                          Open WebUI dropdown (recommended);
                                          also starts Strata on :8095, unloaded.
                                          'nothink': thinking OFF BY DEFAULT; each
                                          client turns it on per request (Claude Code
                                          thinking toggle + /effort, Pi thinking level,
                                          aider --reasoning-effort, Open WebUI Reasoning
                                          Effort). Needs patches/llama-per-request-
                                          thinking.patch. Recommended mode.
       $(basename "$0") strata            start only Strata (if it is not up)
       $(basename "$0") strata off|low|medium|default
                                          ...and set its thinking for EVERY client
                                          (Claude Code, Pi, Open WebUI); 'strata
                                          thinking' shows it. off = best code score
       $(basename "$0") <model> <context>  pin one model, per-model backend
       $(basename "$0") stop      free the GPU completely (SIGTERM, then SIGKILL)
       $(basename "$0") start     relaunch whatever was running last
       $(basename "$0") status
       $(basename "$0") list

Models:
  qwen3.8        Qwen3.8-27B      20.5GB  DENSE 27B, hybrid attn (64L), thinking
                                          UD-Q6_K + MTP: 57 tok/s, 22 at 128k depth
  qwen3.8-mtp    (same as qwen3.8, kept so old commands still work)
  qwen3.8-q8     Qwen3.8-27B Q8_0 27.1GB  near-lossless + MTP: 50 tok/s. 32k/128k
  qwen3.5-uncensored
                 Qwen3.5-27B-Unc. 12.4GB  DENSE 27B, same arch as qwen3.8 one base
                                          back. 32k-128k, ~32 tok/s, no MTP head
  qwen3.5-9b-uncensored
                 Qwen3.5-9B-Unc.  8.9GB   DENSE 9B, same family, half the layers.
                                          Reaches native 256k. 58 tok/s, R9700 only
  gemma4-12b     Gemma 4-12B      13.3GB  DENSE 12B, images (+audio) via mmproj.
                                          Q8_0 + MTP: ~105 tok/s. 128k/256k, R9700

Context: 32k 64k 128k 256k  (only sizes within each model's native trained
range. Two cards since 2026-10-05, a 9070 XT and an R9700, 48.9 GB that
llama.cpp splits every model across; nearly every config now fits with no CPU
offload, so generation barely changes with context. qwen3.8-q8 stops at 128k: 256k leaves under
1 GB on the 9070 XT. 512k/1m are not offered by any model currently
on disk. Run '$(basename "$0") list'.)

Notes:
  * 'router' vs '<model> <context>': the router serves every preset in
    models-preset.ini and loads on demand, so you switch models from the
    client instead of the shell. Both run the same ROCm build and the same
    flags (this script's table mirrors the presets), so pinning a model
    gains no speed; it only keeps one model resident without the router.
  * qwen3.5-9b-uncensored and gemma4-12b run on the R9700 alone (-dev
    ROCm1); every other model splits across both cards.
  * Close DaVinci Resolve first — it holds ~10.4GB VRAM and will cause
    allocation failures on the tighter configs.
  * Gaming: you do not need 'stop'. After ${SLEEP_IDLE}s idle the server
    releases the model and VRAM drops to ~0 on its own, while staying up on
    port ${PORT}; the next request reloads it. Use 'stop' only to kill the
    process outright. Override with SLEEP_IDLE=<seconds>, or -1 to disable.

Examples:
  $(basename "$0") router
  $(basename "$0") qwen3.8 128k
  $(basename "$0") stop
  $(basename "$0") start
  SLEEP_IDLE=-1 $(basename "$0") router            # never sleep
USAGE
}

list_combos() {
  echo "Verified model/context combinations (backend shown per context):"
  for model in qwen3.8 qwen3.8-mtp qwen3.8-q8 qwen3.5-uncensored qwen3.5-9b-uncensored gemma4-12b; do
    printf '  %-21s ' "$model"
    for ctx in 16k 32k 64k 128k 192k 200k 256k 512k 1m; do
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
  echo "  rocm = build/  (single backend — Vulkan retired)"
  echo
  # Router presets are a separate set: whatever models-preset.ini defines, which
  # includes models with no pinned config above (and the -nothink variants).
  echo "Router presets ($(basename "$0") router; pick in the client by name):"
  if [[ -r "$PRESET" ]]; then
    grep -oE '^\[[^]*][^]]*\]' "$PRESET" | tr -d '[]' | sed 's/^/  /'
  else
    echo "  ($PRESET not found)"
  fi
}

# SIGTERM first — llama-server shuts down cleanly on it. In router mode
# (--models-preset) this matches both the router and the child process it
# spawned per model, since both are named llama-server.
stop_server() {
  if ! pgrep -x llama-server > /dev/null 2>&1 && ! pgrep -x llama-cli > /dev/null 2>&1; then
    echo "No llama-server running. VRAM in use: $(vram_report)"
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
  echo "==> Stopped. VRAM in use: $(vram_report)"
}

start_router() {
  # 'nothink': --reasoning-budget 0 on the router's own command line. Router
  # arguments outrank every preset's settings (llama.cpp server README,
  # "precedence rule for preset options") and are passed to each child, so
  # every model's DEFAULT is thinking off. Thinking off scored 48/50 against 35
  # on Qwen3.8 Q6 and 43 against 42 on Q8 (benchmarks/qwen3.8-27B-UD-Q6_K/
  # fixed-prompts/SUMMARY.txt); Qwen3.5-27B and Nemotron Bolt want it on.
  # Since 2026-11-06 it is only a default: with patches/llama-per-request-
  # thinking.patch applied to ~/llama.cpp, a request turns thinking on or off:
  #   OpenAI  reasoning_effort none = off, minimal 1K, low 2K, medium 8K, high
  #           unlimited; or an explicit reasoning_budget_tokens. No field = default.
  #   Anthropic  no "thinking" or "disabled" = off; "enabled" = its budget_tokens;
  #           "adaptive" (Claude Code) = on, budget from output_config.effort.
  # Keep 'nothink': Pi's "off" and aider's unset send NO field, so the default
  # must be off. Unpatched llama.cpp ignores Claude Code's thinking fields.
  local mode="${1:-}" think_args=()
  case "$mode" in
    "")      ;;
    nothink) think_args=(--reasoning-budget 0) ;;
    *) echo "Error: router takes no option or 'nothink' (got '$mode')." >&2; exit 1 ;;
  esac
  # ROUTER_BIN: run the router (and so every preset) on another build, e.g. the
  # RDNA fork for the -tensor trial presets (models-preset.ini). Not remembered
  # by 'start': set it again.
  local bin="${ROUTER_BIN:-$LLAMA_DIR/$ROUTER_BACKEND/bin/llama-server}"
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
  echo "    binary: $bin (applies to every model — see notes)"
  echo "    models-max: $MODELS_MAX"
  if (( SLEEP_IDLE > 0 )); then
    # Not in unset_reserved_args(), so children inherit it and each loaded model
    # releases its own VRAM after idling.
    echo "    idle sleep: ${SLEEP_IDLE}s (inherited by each spawned model)"
  fi
  mkdir -p "$(dirname "$STATE")"
  printf 'router %s\n' "$mode" > "$STATE"
  [[ "$mode" == nothink ]] && echo "    thinking: OFF by default (--reasoning-budget 0); clients turn it on per request"
  cd "$LLAMA_DIR"
  nohup "$bin" --models-preset "$PRESET" --models-max "$MODELS_MAX" \
    --sleep-idle-seconds "$SLEEP_IDLE" ${think_args[@]+"${think_args[@]}"} \
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

  echo "==> Router live at http://$(hostname).local:${PORT} ($(hostname -I | cut -d' ' -f1)) — presets available:"
  curl -s "http://localhost:${PORT}/v1/models" 2>/dev/null | python3 -c '
import json, sys
for m in json.load(sys.stdin)["data"]:
    print("     ", m["id"], "" if m.get("status", {}).get("value") != "loaded" else "[loaded]")
' 2>/dev/null || echo "     (could not list — see $LOG)"
  start_strata
}

# Strata (Qwen3.8-Flash-Next, strata.md) is its own server on 8095: the router
# can only spawn llama-server. It starts with the router but lazily
# ("lazy_load": true in its config), so the cards stay free until its first
# request; its before_load hook then unloads the router model, and it unloads
# itself after 15 idle minutes. 'stop' leaves it alone.
STRATA_DIR="$HOME/code/Strata"
# IQ3_XXS needs STRATA_RESIDENT_HEADROOM_GIB=12 in its config, or it OOM-kills the
# desktop on this 30 GB box (strata.md). STRATA_RUN overrides the script.
STRATA_RUN="${STRATA_RUN:-$STRATA_DIR/run-iq3_xxs.sh}"
STRATA_PORT=8095

strata_up() {
  curl -s --max-time 3 "http://localhost:${STRATA_PORT}/health" 2>/dev/null | grep -q '"service": *"strata"'
}

start_strata() {
  if [[ ! -x "$STRATA_RUN" ]]; then
    echo "==> Strata: $STRATA_RUN not found, skipped"; return 0
  fi
  if strata_up; then
    echo "==> Strata already up on :${STRATA_PORT}"; return 0
  fi
  # exec: the subshell becomes Strata. Without it the backgrounded `cd && nohup`
  # list stayed behind as a bash waiting on Strata, holding the caller's stdout
  # open, so `switch-model.sh router | ...` never returned.
  (cd "$STRATA_DIR" && exec nohup "$STRATA_RUN") > "$STRATA_DIR/strata-server.out" 2>&1 < /dev/null &
  disown
  for _ in $(seq 1 20); do
    strata_up && break
    sleep 3
  done
  if strata_up; then
    echo "==> Strata live at http://$(hostname).local:${STRATA_PORT} (loads on its first request)"
  else
    echo "WARNING: Strata did not come up. Check $STRATA_DIR/strata-server.out" >&2
  fi
}

# Strata's thinking, for every client at once: no restart, no model load, and
# kept across Strata restarts (its shared settings file). Why server-side: with
# thinking turned off, Claude Code still sends output_config.effort "high",
# which Strata maps to xhigh -- the level that once thought 100K tokens without
# answering (strata.md). No client sends reasoning_budget_tokens, so the shared
# budget caps every client; the shared effort covers clients that send none.
# Code quality (benchmarks/qwen3.8-flash-next-IQ3_XXS-strata/fixed-prompts):
# thinking off 48/50, medium 44/50. Router models ignore this: use a -nothink
# preset (models-preset.ini).
STRATA_CONFIG="$STRATA_DIR/strata-iq3_xxs.json"

strata_think() {
  local level="$1" key effort budget
  key=$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("api_key",""))' "$STRATA_CONFIG") \
    || { echo "cannot read the API key from $STRATA_CONFIG" >&2; return 1; }
  local url="http://localhost:${STRATA_PORT}/settings" auth="Authorization: Bearer $key"
  case "$level" in
    off)      effort=none;   budget=1 ;;      # budget 1 also closes Claude Code's "high"
    low)      effort=low;    budget=2048 ;;
    medium)   effort=medium; budget=8192 ;;
    default)  effort="";     budget="" ;;
    thinking) effort=keep ;;
    *) echo "strata thinking: off, low, medium or default (got '$level')" >&2; return 1 ;;
  esac
  if [[ "$effort" != keep ]]; then
    # Change only the two thinking keys; the web Chat's other shared settings stay.
    local body
    body=$(curl -sS --max-time 10 -H "$auth" "$url" | python3 -c '
import json, sys
d = json.load(sys.stdin).get("defaults") or {}
for k, v in (("reasoning_effort", sys.argv[1]), ("reasoning_budget_tokens", sys.argv[2])):
    if v == "":
        d.pop(k, None)
    else:
        d[k] = int(v) if k == "reasoning_budget_tokens" else v
print(json.dumps({"defaults": d or None}))' "$effort" "$budget") \
      || { echo "could not read Strata's settings" >&2; return 1; }
    curl -sS --max-time 10 -X POST -H 'Content-Type: application/json' -H "$auth" \
      -d "$body" "$url" > /dev/null || { echo "Strata refused the change" >&2; return 1; }
  fi
  curl -sS --max-time 10 -H "$auth" "$url" | python3 -c '
import json, sys
d = json.load(sys.stdin).get("defaults") or {}
e, b = d.get("reasoning_effort"), d.get("reasoning_budget_tokens")
print("==> Strata thinking: " + ("clients decide (xhigh when a client asks for none)" if e is None and b is None
      else "effort %s, budget %s tokens, for every client" % (e or "(client)", b or "none")))'
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
    echo "==> Restarting last config: router ${ctx:-}"
    start_router "${ctx:-}"
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
  echo "VRAM in use: $(vram_report)"
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
  vram_before=$(vram_used)
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
  # --ctx-checkpoints 4 mirrors [*] in models-preset.ini: the default 32 filled
  # 25 GB of RAM on a long Qwen3.8 agent turn and hung the server.
  # shellcheck disable=SC2086
  nohup "$bin" -m "models/$file" -ngl 99 -c "$tokens" $extra -np 1 --load-mode dio --ctx-checkpoints 4 \
    --sleep-idle-seconds "$SLEEP_IDLE" \
    --host "$HOST" --port "$PORT" > "$LOG" 2>&1 < /dev/null &
  disown

  echo "==> Waiting for health check..."
  local ok=0 st
  # A large file (Qwen3.8-27B Q8_0, 29 GB, the largest left) can take a
  # couple of minutes to load cold.
  for _ in $(seq 1 80); do
    # DFlash always emits "[spec] failed to measure draft model memory: failed
    # to create llama_context" during its memory-fitting probe, and the log
    # itself calls that normal. Filter it out or every muse-glimmer launch
    # aborts on a healthy server. Build 11345 does the same for Gemma 4's MTP
    # drafter, worded differently: "failed to measure the memory of the extra
    # model, fitting without it: failed to create llama_context" (found
    # 2026-10-06; every gemma4 config aborted here while the server was up).
    if grep -i 'failed to \(allocate\|create\)' "$LOG" 2>/dev/null \
         | grep -v '\[spec\] failed to measure' \
         | grep -qv 'failed to measure the memory of the extra model'; then
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

  echo "==> Loaded. VRAM: $(vram_report)"
  grep -iE 'kv_cache: size|recurrent: size' "$LOG" | tail -2 || true

  echo "==> Test request:"
  # max_tokens is a cap, not a reservation — a trivial reply still costs three
  # tokens. But every thinking model here spends the budget on reasoning FIRST,
  # so a small cap truncates mid-think and returns empty content, which reads as
  # a broken load when the server is fine. Keep this at 12k+.
  curl -s "http://localhost:${PORT}/v1/chat/completions" -H 'Content-Type: application/json' \
    -d '{"messages":[{"role":"user","content":"Say hi in three words."}],"max_tokens":12288}' \
    | python3 -c '
import json, sys
d = json.load(sys.stdin)
m = d["choices"][0]["message"]
print(m.get("content") or m.get("reasoning_content", "")[:100])
' 2>/dev/null || echo "  (request sent — see $LOG if this looks wrong)"

  echo "==> ${MODEL_LABEL[$model]} is live at http://$(hostname).local:${PORT} ($(hostname -I | cut -d' ' -f1))"
}

case "${1:-}" in
  ""|-h|--help) usage ;;
  status) status ;;
  list) list_combos ;;
  stop) stop_server ;;
  start) start_last ;;
  router) start_router "${2:-}" ;;
  strata) start_strata
          if [[ -n "${2:-}" ]]; then strata_think "$2"; fi ;;
  *)
    if [[ $# -lt 2 ]]; then usage; exit 1; fi
    switch_model "$1" "$2"
    ;;
esac
