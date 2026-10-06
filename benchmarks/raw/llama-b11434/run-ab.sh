#!/usr/bin/env bash
# llama.cpp build 11345 (a868c3e3c) vs b11434 (5e03bdd87), 2026-10-06, router down.
# Same presets, same probe, both builds; at temp 0 (comparable with every earlier
# figure) and at temp 1.0 (the presets' own sampling, where upstream #27694
# changed how MTP drafts are accepted). Then the 128K depth test on the new build.
R=/home/nipuna/code/local-llm-benchmarks/benchmarks/raw
D=$R/llama-b11434
OLD=/home/nipuna/llama.cpp/build/bin/llama-server
NEW=/home/nipuna/llama.cpp-b11434/build/bin/llama-server
P=(qwen3.8-27B-32k qwen3.8-27B-q8-128k gemma4-26B-A4B-32k qwen3.6-35B-A3B-128k
   laguna-33B-A3B-32k glm-4.7-flash-30B-A3B-32k muse-glimmer-30B-32k gpt-oss-20b-A3.6B-32k)
cd "$R/r9700-two-cards"
export PRESETS=/home/nipuna/code/local-llm-benchmarks/models-preset.ini
mkdir -p "$D/logs-old" "$D/logs-new"
for t in 0.0 1.0; do
  for b in old new; do
    bin=$OLD; [ $b = new ] && bin=$NEW
    echo "=== $(date -Is) build=$b temp=$t"
    BIN=$bin PROBE_TEMP=$t LOGDIR=$D/logs-$b python3 preset_probe.py "$D/ab-$b-t$t.txt" "${P[@]}"
  done
done
echo "=== $(date -Is) depth.sh on b11434"
BIN=$NEW LOGDIR=$D/logs-new bash depth.sh
echo "=== $(date -Is) done"
