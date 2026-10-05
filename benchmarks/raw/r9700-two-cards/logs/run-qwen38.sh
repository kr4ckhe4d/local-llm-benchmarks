#!/usr/bin/env bash
cd /home/nipuna/code/local-llm-benchmarks/benchmarks/raw/r9700-two-cards
export LOGDIR=/home/nipuna/code/local-llm-benchmarks/benchmarks/raw/r9700-two-cards/logs
{ echo "=== $(date -Is) dense.sh qwen38"; bash dense.sh qwen38; echo "=== $(date -Is) depth.sh"; bash depth.sh; echo "=== $(date -Is) done"; } 2>&1 | tee $LOGDIR/qwen38-rerun.txt
