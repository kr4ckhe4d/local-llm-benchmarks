#!/usr/bin/env bash
# KL-divergence of a quantised model against an unquantised reference.
#
# Added 2026-08-21. This is the instrument for the question `code-quality-test.py`
# cannot answer: that probe resolves 4 checks in 50 across a 68-76% band, which
# is far too coarse to order quant tiers. KLD measures the distribution shift
# the quantisation itself causes, per token, with error bars.
#
#   ./kld-test.sh base  Qwen3.8-27B-BF16-00001-of-00002.gguf 100 "-ngl 16"
#   ./kld-test.sh score qwen3.8-27B-UD-Q6_K-v3 Qwen3.8-27B-UD-Q6_K-v3.gguf 100 "-ngl 40"
#
# TWO THINGS MUST MATCH between a base run and every score run against it, or
# the numbers are meaningless: `-c` (fixed at 512 here, the llama.cpp KLD
# convention) and `--chunks`. The score mode re-reads both out of the base file
# header and refuses to run on a mismatch, so this cannot go wrong silently.
#
# `Same top p` in the output is top-1 agreement -- the metric Unsloth's
# ">10% top-1%" claim is stated in, which is why it is pulled into the summary.
#
# Sizing: the base file holds logits only for the SCORED half of each window
# (255 of every 512 tokens), at 2*(n_vocab rounded up)+4 uint16 per token.
# For Qwen3.8's 248,320-token vocab that is 496,648 B per scored token:
#   100 chunks -> 51,200 prefilled, 25,500 scored, 12.66 GB on disk.
# REGENERATING THE REFERENCE AND BASE FILE
# ----------------------------------------
# The BF16 weights (54.66 GB) and the base logits file (25.33 GB) were deleted
# after measuring -- they are needed only to RE-measure, and the results they
# produced live in benchmarks/<model>/kld.txt. To rebuild both:
#
#   R=https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/resolve/main/BF16
#   cd ~/llama.cpp/models
#   curl -L -C - -O $R/Qwen3.8-27B-BF16-00001-of-00002.gguf
#   curl -L -C - -O $R/Qwen3.8-27B-BF16-00002-of-00002.gguf
#
# sha256 (verify these -- Unsloth re-quantises in place under the same names):
#   00001  b9966e82b7a4d87028b5eae061d578ee826305ebf8baea5bfc6e09bad0ba191f
#   00002  92e3943c4f9bd6292a7bef82369f65fed9bfed088b9df0fb2fa2ce17c9edfa02
#
# Corpus (13 MB, kept):  ~/llama.cpp/kld/wikitext-2-raw/wiki.test.raw
#   from https://huggingface.co/datasets/ggml-org/ci/resolve/main/wikitext-2-raw-v1.zip
#
# Then, exactly as the 2026-08-21 run:
#   ./kld-test.sh base Qwen3.8-27B-BF16-00001-of-00002.gguf 200 "-ngl 0 -t 16"
# 16m49s CPU-only, peak RSS 54.9 GB against 62 GB, no swap. Do NOT partially
# offload the BF16 pass: -ngl 16 measured 56 tok/s prefill against 107 at
# -ngl 0, i.e. partial GPU offload is 2x SLOWER here.

set -uo pipefail

LLAMA_DIR="$HOME/llama.cpp"
BIN="$LLAMA_DIR/build/bin/llama-perplexity"
MODEL_DIR="$LLAMA_DIR/models"
HERE="$(cd "$(dirname "$0")" && pwd)"
KLD_DIR="${KLD_DIR:-$LLAMA_DIR/kld}"
CORPUS="${CORPUS:-$KLD_DIR/wikitext-2-raw/wiki.test.raw}"
BASE_FILE="${BASE_FILE:-$KLD_DIR/qwen3.8-27B-bf16.kld}"
CTX=512                       # KLD convention; do not change without regenerating the base
VRAM=/sys/class/drm/card1/device/mem_info_vram_used
GTT=/sys/class/drm/card1/device/mem_info_gtt_used

mib() { echo $(( $(cat "$1") / 1048576 )); }
die() { echo "$*" >&2; exit 2; }

[ -f "$CORPUS" ] || die "no corpus at $CORPUS"
MODE="${1:?usage: $0 base|score ...}"; shift

case "$MODE" in
base)
  MODEL="${1:?model.gguf}"; CHUNKS="${2:-100}"; EXTRA="${3:--ngl 16}"
  [ -f "$MODEL_DIR/$MODEL" ] || die "no such model: $MODEL_DIR/$MODEL"
  mkdir -p "$KLD_DIR"
  echo "==> base: $MODEL, $CHUNKS chunks -> $BASE_FILE"
  echo "    VRAM before: $(mib $VRAM) MiB, GTT $(mib $GTT) MiB"
  # shellcheck disable=SC2086
  "$BIN" -m "$MODEL_DIR/$MODEL" -f "$CORPUS" -c "$CTX" --chunks "$CHUNKS" \
         $EXTRA --kl-divergence-base "$BASE_FILE"
  rc=$?
  echo "    VRAM after: $(mib $VRAM) MiB, GTT $(mib $GTT) MiB"
  [ $rc -eq 0 ] || die "base generation failed rc=$rc"
  ls -la "$BASE_FILE"
  ;;
score)
  LABEL="${1:?label}"; MODEL="${2:?model.gguf}"; CHUNKS="${3:-100}"; EXTRA="${4:--ngl 99}"
  [ -f "$MODEL_DIR/$MODEL" ] || die "no such model: $MODEL_DIR/$MODEL"
  [ -f "$BASE_FILE" ] || die "no base file at $BASE_FILE -- run '$0 base' first"

  # Refuse a silent mismatch. The base header is: "_logits_" (8B), n_ctx (i32),
  # n_vocab (i32), n_chunk (i32).
  read -r B_CTX B_CHUNKS < <(python3 - "$BASE_FILE" <<'PY'
import struct,sys
with open(sys.argv[1],'rb') as f:
    assert f.read(8)==b'_logits_', 'not a llama.cpp KLD base file'
    ctx,vocab,chunks = struct.unpack('<iii', f.read(12))
print(ctx, chunks)
PY
) || die "cannot read base header"
  [ "$B_CTX" = "$CTX" ] || die "base was built at -c $B_CTX, this run uses $CTX"
  [ "$B_CHUNKS" = "$CHUNKS" ] || die "base has $B_CHUNKS chunks, this run asks for $CHUNKS"

  OUTDIR="$HERE/$LABEL"; mkdir -p "$OUTDIR"
  OUT="$OUTDIR/kld.txt"
  {
    printf '# KL-divergence vs unquantised reference\n'
    printf '# model  : %s\n# base   : %s\n# corpus : %s\n' \
           "$MODEL" "$(basename "$BASE_FILE")" "$(basename "$CORPUS")"
    printf '# window : -c %s, --chunks %s (%s tokens prefilled, %s scored)\n' \
           "$CTX" "$CHUNKS" "$((CTX*CHUNKS))" "$((255*CHUNKS))"
    printf '# flags  : %s\n# host   : %s, llama.cpp %s\n# date   : %s\n\n' \
           "$EXTRA" "$(uname -sr)" "$("$BIN" --version 2>&1 | head -1)" "$(date -Is)"
    # shellcheck disable=SC2086
    "$BIN" -m "$MODEL_DIR/$MODEL" -f "$CORPUS" -c "$CTX" --chunks "$CHUNKS" \
           $EXTRA --kl-divergence --kl-divergence-base "$BASE_FILE" 2>&1
    printf '\nVRAM %s MiB | GTT %s MiB\n' "$(mib $VRAM)" "$(mib $GTT)"
  } | tee "$OUT" | grep -E "Mean KLD|Mean Δp|RMS Δp|Same top p|Final estimate|99.0%   KLD"
  echo "==> $OUT"
  ;;
*) die "usage: $0 base|score ..." ;;
esac
