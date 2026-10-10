#!/usr/bin/env bash
# Strata's "before_load" hook: unload whatever the llama.cpp router has loaded,
# so Strata gets both cards. Strata (IQ3_XXS) fills ~32 GB + ~16 GB; with a
# router model still resident its expert cache would come up short or fail.
#
# Wired in ~/code/Strata/strata-iq3_xxs.json:
#   "before_load": "/home/nipuna/code/local-llm-benchmarks/strata-before-load.sh"
#   "idle_unload_s": 900
# The other direction (Strata unloads before a router model loads) is done by
# claude-local.sh for Claude Code; Open WebUI has no such hook. See strata.md.
set -uo pipefail

ROUTER="${ROUTER:-http://127.0.0.1:8090}"

loaded() {
  curl -sS --max-time 5 "$ROUTER/models" 2>/dev/null \
    | python3 -c 'import sys,json
for m in json.load(sys.stdin)["data"]:
    if m.get("status",{}).get("value") != "unloaded": print(m["id"])' 2>/dev/null
}

for m in $(loaded); do
  echo "strata-before-load: unloading router model $m"
  curl -sS --max-time 10 -o /dev/null -H 'Content-Type: application/json' \
    -d "{\"model\":\"$m\"}" "$ROUTER/models/unload"
done

# The unload returns before the child process exits and frees its VRAM.
for _ in $(seq 1 60); do
  [ -z "$(loaded)" ] && exit 0
  sleep 1
done
echo "strata-before-load: router models still loaded after 60 s" >&2
exit 0   # load anyway; Strata sizes its cache from the VRAM it finds free
