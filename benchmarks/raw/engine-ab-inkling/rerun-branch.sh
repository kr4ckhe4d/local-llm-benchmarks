#!/usr/bin/env bash
# re-run the branch arm with the router stopped; the router comes back however this ends
cd "$(dirname "$0")"
trap '$HOME/code/local-llm-benchmarks/switch-model.sh start' EXIT
$HOME/code/local-llm-benchmarks/switch-model.sh stop
ARMS=llama-q8-branch ./run.sh
