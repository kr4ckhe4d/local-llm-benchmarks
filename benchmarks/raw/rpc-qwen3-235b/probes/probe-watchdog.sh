#!/usr/bin/env bash
# Load config A with a watchdog: log per-card VRAM/GTT every 0.2 s, kill llama-bench if MemAvailable < 8 GiB.
M=/mnt/fast/models/qwen3-235b/Qwen3-235B-A22B-Instruct-2507-UD-Q3_K_XL-00001-of-00003.gguf
~/llama-rpc/build-vk/bin/llama-bench -m $M --rpc 10.10.10.2:50053 -lm none -ngl 99 -fa 1 -dev "$DEV" -ts "$TS" -p 64 -n 16 -r 1 > "$OUT.json" 2> "$OUT.log" &
pid=$!
while kill -0 $pid 2>/dev/null; do
  a=$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo)
  line="$(date +%T.%N | cut -c1-10) avail=${a}MiB"
  for c in card0 card1; do d=/sys/class/drm/$c/device
    line="$line $c(vram=$(( $(cat $d/mem_info_vram_used)/1048576 )) gtt=$(( $(cat $d/mem_info_gtt_used)/1048576 )))"
  done
  echo "$line"
  if [ "$a" -lt 8192 ]; then echo "WATCHDOG: killing llama-bench at ${a} MiB available"; kill -9 $pid; fi
  sleep 0.2
done
wait $pid; echo "exit $?"
