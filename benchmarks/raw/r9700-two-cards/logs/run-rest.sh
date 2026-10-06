#!/usr/bin/env bash
# Everything not yet captured on two cards, 2026-10-06. Router down.
D=/home/nipuna/code/local-llm-benchmarks/benchmarks/raw/r9700-two-cards
cd "$D"
export LOGDIR=$D/logs DIO=1
echo "=== $(date -Is) A. moe_sweep.py: qwen3.6, laguna, glm vs the single-card presets"
PRESETS=$D/logs/presets-4c4b695.ini python3 moe_sweep.py logs/moe-rest-sweep.txt \
  qwen3.6-35B-A3B-32k qwen3.6-35B-A3B-128k qwen3.6-35B-A3B-256k \
  laguna-33B-A3B-32k laguna-33B-A3B-128k laguna-33B-A3B-256k \
  laguna-33B-A3B-q8-32k laguna-33B-A3B-q8-128k laguna-33B-A3B-q8-256k \
  glm-4.7-flash-30B-A3B-32k glm-4.7-flash-30B-A3B-128k glm-4.7-flash-30B-A3B-200k
echo "=== $(date -Is) B. dense.sh rest: Qwen3.5-27B 64k, Muse 64k/128k"
bash dense.sh rest
echo "=== $(date -Is) C. preset_probe.py: presets never measured on two cards"
unset DIO
PRESETS=/home/nipuna/code/local-llm-benchmarks/models-preset.ini python3 preset_probe.py logs/presets-unmeasured.txt \
  gpt-oss-20b-A3.6B-32k gpt-oss-20b-A3.6B-128k \
  qwen3.5-9B-uncensored-32k qwen3.5-9B-uncensored-128k qwen3.5-9B-uncensored-256k \
  muse-glimmer-30B-32k qwen3.5-27B-uncensored-32k qwen3.5-27B-uncensored-128k
echo "=== $(date -Is) done"
