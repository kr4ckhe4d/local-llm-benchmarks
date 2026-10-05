#!/usr/bin/env bash
# Gemma 4 rows of the MoE sweep, rerun with captured output. "As written" is the
# single-card preset file at 4c4b695 (copied beside this script).
D=/home/nipuna/code/local-llm-benchmarks/benchmarks/raw/r9700-two-cards
cd "$D"
export LOGDIR=$D/logs PRESETS=$D/logs/presets-4c4b695.ini DIO=1
rm -f logs/gemma-sweep.txt
echo "=== $(date -Is) moe_sweep.py gemma4"
python3 moe_sweep.py logs/gemma-sweep.txt \
  gemma4-26B-A4B-32k gemma4-26B-A4B-128k gemma4-26B-A4B-256k \
  gemma4-26B-A4B-vision-32k gemma4-26B-A4B-vision-128k \
  gemma4-26B-A4B-q8-32k gemma4-26B-A4B-q8-128k gemma4-26B-A4B-q8-256k
echo "=== $(date -Is) done"
