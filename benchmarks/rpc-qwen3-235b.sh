#!/usr/bin/env bash
# Qwen3-235B-A22B-Instruct-2507 UD-Q3_K_XL (97.0 GiB) across this PC and ubuntulocal over llama.cpp RPC.
# Client: ~/llama-rpc (b94959a64) ROCm+RPC build, ROCm 7.2.4. Devices: ROCm0 = RX 9070 XT, ROCm1 = R9700.
# Server: ubuntulocal rpc-server, Vulkan build at the same commit, 10.10.10.2:50053: RPC0 = B580, RPC1 = 5950X/DDR4.
# Layer splits from rpc-split.py.
#
# Safety, after two OOM freezes on 2026-11-20 (see rpc-qwen3-235b.md):
#  - -lm none: the default mmap maps all 97 GiB on this 30 GB box.
#  - each run is in a 22 GB scope (anonymous memory), and a watchdog kills llama-bench if MemAvailable
#    drops under 8 GiB, which also covers GPU-driver (GTT) memory the scope does not count.
set -uo pipefail
OUT=${OUT:-$HOME/code/local-llm-benchmarks/benchmarks/raw/rpc-qwen3-235b}
B=$HOME/llama-rpc/build/bin/llama-bench
M=/mnt/fast/models/qwen3-235b/Qwen3-235B-A22B-Instruct-2507-UD-Q3_K_XL-00001-of-00003.gguf
R=10.10.10.2:50053
export HIP_VISIBLE_DEVICES=0,1   # hide the iGPU
mkdir -p "$OUT"
common=(-m "$M" --rpc "$R" -lm none -ngl 99 -fa 1 -o json)

watchdog() {
    while true; do
        a=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
        if [ "$a" -lt 8192 ]; then echo "   WATCHDOG $(date +%T): ${a} MiB available, killing llama-bench"; pkill -9 -x llama-bench; fi
        sleep 0.3
    done
}

run() {  # label, args...
    local label=$1; shift
    echo "== $(date +%T) $label: $*"
    watchdog & local wd=$!
    systemd-run --user --scope -q -p MemoryMax=22G -p MemorySwapMax=0 \
        "$B" "${common[@]}" "$@" > "$OUT/$label.json" 2> "$OUT/$label.log"
    echo "   exit $? $(date +%T)"
    kill $wd 2>/dev/null; wait $wd 2>/dev/null
    python3 - "$OUT/$label.json" <<'EOF'
import json, sys
try:
    for r in json.load(open(sys.argv[1])):
        t = ("pp%d" % r["n_prompt"]) if r["n_prompt"] else ("tg%d" % r["n_gen"])
        print(f"   {t} @ {r['n_depth']}: {r['avg_ts']:.2f} +/- {r['stddev_ts']:.2f} tok/s")
except Exception as e:
    print("   no results:", e)
EOF
}

# A: budgets 12 / 24 / 8.5 GiB, rest on the server CPU (53.8 GiB there)
run a-4dev -dev ROCm0/ROCm1/RPC0/RPC1 -ts 11/23/8/52 -p 512 -n 128 -r 2
# A2: budgets 13.5 / 29.5 / 9 GiB, like the ROCm presets load the R9700
run a2-4dev-full -dev ROCm0/ROCm1/RPC0/RPC1 -ts 13/28/8/45 -p 512 -n 128 -r 2
# C: A2 + this PC's RAM: the R9700 takes 10 more layers (41-50) whose experts sit in local RAM (~10 GiB);
#    the server keeps 35
run c-localram -dev ROCm0/ROCm1/RPC0/RPC1 -ts 13/38/8/35 \
    -ot 'blk\.(4[1-9]|50)\.ffn_(up|down|gate)_exps\.weight=CPU' -p 512 -n 128 -r 2
echo "== $(date +%T) DONE"
