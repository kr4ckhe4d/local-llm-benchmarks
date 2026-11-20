#!/usr/bin/env bash
# Vulkan vs SYCL llama-bench on the Intel Arc B580 (ubuntulocal).
# Runs ON the server; writes one llama-bench JSON per (backend, label) to $OUT.
#
#   ./arc-b580-bench.sh <label> <model.gguf> [extra llama-bench args...]
#
# Both backends get identical args: -ngl 99 -fa 1, pp512 + tg128, plus the
# same two tests 16K tokens deep. SYCL is pinned to Level Zero.
set -euo pipefail
label=$1 model=$2; shift 2
OUT=${OUT:-$HOME/bench/arc-b580}
LLAMA=${LLAMA:-$HOME/llama.cpp}
REPS=${REPS:-3}
mkdir -p "$OUT"

run() {  # backend, bindir
    local be=$1 bin=$2; shift 2
    echo "== $be $label" >&2
    "$bin/llama-bench" -m "$model" -ngl 99 -fa 1 -p 512 -n 128 -d 0,16384 -r "$REPS" "$@" \
        -o json > "$OUT/$be-$label.json" 2> "$OUT/$be-$label.log"
}

run vulkan "$LLAMA/build/bin" "$@"
(
    set +u; source /opt/intel/oneapi/setvars.sh > /dev/null 2>&1; set -u
    export ONEAPI_DEVICE_SELECTOR=level_zero:0
    run sycl "$LLAMA/build-sycl/bin" "$@"
)
