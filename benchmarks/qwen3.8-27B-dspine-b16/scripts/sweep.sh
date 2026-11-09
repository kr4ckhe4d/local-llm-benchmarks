#!/bin/bash
S=${S:-$(dirname "$0")/out}; mkdir -p $S
OUT=$S/sweep.jsonl; : > $OUT
B=~/llama.cpp/build/bin/llama-server; M=/mnt/fast/models; PORT=18099
T="-m $M/Qwen3.8-27B-UD-Q6_K.gguf -ngl 99 -c 32768 -np 1 -fa on -ctk q8_0 -ctv q8_0 -ub 1024 --load-mode dio --port $PORT"
DS=$M/Qwen3.8-27B-DSpine-b16-nobridge-Q8_0.gguf; DF=$M/Qwen3.8-27B-DFlash2-Q8_0.gguf
run() { label=$1; nmax=$2; shift 2
  echo "=== $label $(date +%T)"
  for i in $(seq 30); do ss -ltn | grep -q ":$PORT " || break; sleep 2; done
  if ss -ltn | grep -q ":$PORT "; then echo "port busy, skipping $label failed"; return; fi
  $B $T "$@" > $S/srv-$label.log 2>&1 & pid=$!
  for i in $(seq 100); do sleep 3; kill -0 $pid 2>/dev/null || break; curl -s -m 2 localhost:$PORT/health | grep -q ok && break; done
  if ! kill -0 $pid 2>/dev/null; then echo "server died, $label failed"; tail -3 $S/srv-$label.log; return; fi
  python3 "$(dirname "$0")/specbench.py" http://127.0.0.1:$PORT $label $nmax $OUT || echo "bench failed $label"
  kill $pid; wait $pid; sleep 8
}
trap 'kill $pid 2>/dev/null' EXIT
run none 0
run mtp 3 --spec-type draft-mtp
run dflash2-n5 5 --model-draft $DF --spec-type draft-dflash --spec-draft-ngl 999 --spec-draft-n-max 5
run dflash2-n7 7 --model-draft $DF --spec-type draft-dflash --spec-draft-ngl 999 --spec-draft-n-max 7
for n in 3 5 7 15; do
  run dspine-nb-causal-n$n $n --model-draft $DS --spec-type draft-dflash --spec-draft-ngl 999 --spec-draft-n-max $n
done
for n in 5 15; do
  run dspine-nb-noncausal-n$n $n --model-draft $DS --spec-type draft-dflash --spec-draft-ngl 999 --spec-draft-n-max $n --override-kv dflash.attention.causal=bool:false
done
echo DONE $(date +%T)
