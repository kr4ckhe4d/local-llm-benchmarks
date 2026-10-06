#!/usr/bin/env bash
# Resume of run-ab.sh after a power cut at 09:04 on 2026-10-06. The old build at
# temp 0 had finished all 8 presets and the new build 1 (qwen3.8-27B-32k); this
# runs the rest with the same settings, appending to the same files.
R=/home/nipuna/code/local-llm-benchmarks/benchmarks/raw
D=$R/llama-b11434
OLD=/home/nipuna/llama.cpp/build/bin/llama-server
NEW=/home/nipuna/llama.cpp-b11434/build/bin/llama-server
P=(qwen3.8-27B-32k qwen3.8-27B-q8-128k gemma4-26B-A4B-32k qwen3.6-35B-A3B-128k
   laguna-33B-A3B-32k glm-4.7-flash-30B-A3B-32k muse-glimmer-30B-32k gpt-oss-20b-A3.6B-32k)
cd "$R/r9700-two-cards"
export PRESETS=/home/nipuna/code/local-llm-benchmarks/models-preset.ini
echo "=== $(date -Is) build=new temp=0.0 (resumed)"
BIN=$NEW PROBE_TEMP=0.0 LOGDIR=$D/logs-new python3 preset_probe.py "$D/ab-new-t0.0.txt" "${P[@]:1}"
for b in old new; do
  bin=$OLD; [ $b = new ] && bin=$NEW
  echo "=== $(date -Is) build=$b temp=1.0"
  BIN=$bin PROBE_TEMP=1.0 LOGDIR=$D/logs-$b python3 preset_probe.py "$D/ab-$b-t1.0.txt" "${P[@]}"
done
echo "=== $(date -Is) depth.sh on b11434"
BIN=$NEW LOGDIR=$D/logs-new bash depth.sh
echo "=== $(date -Is) done"
