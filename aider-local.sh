#!/usr/bin/env bash
# Run aider against the llama.cpp router instead of a hosted API. Sibling to
# claude-local.sh -- same router, different client. This is for interactive
# use: you sit at the terminal and approve aider's own prompts yourself, so
# the --yes-always shell-command gap documented in aider-harness.md (gotcha 2)
# does not apply here -- "Run shell command?" just asks you, normally, and
# you say yes. For a fully unattended/--yes-always flow, that gap DOES apply
# and needs the Python-level monkeypatch in aider-driver/driver.py instead of
# this script.
#
#   aider-local.sh list                      what the router is serving
#   aider-local.sh                           default model, interactive
#   aider-local.sh qwen3.8-27B-128k          pick a model
#   aider-local.sh qwen3.8-27B-128k --yes-always -m "fix the bug"
#
# Written for macOS too, so bash 3.2: no associative arrays, no ${x,,}.
set -uo pipefail

ROUTER="${ROUTER:-http://127.0.0.1:8090}"
DEFAULT_MODEL="${AIDER_LOCAL_MODEL:-qwen3.8-27B-128k}"

die() { printf 'error: %s\n' "$1" >&2; exit 1; }

reachable() {
  curl -sS --max-time 8 -o /dev/null "$ROUTER/v1/models" 2>/dev/null
}

models() {
  curl -sS --max-time 15 "$ROUTER/v1/models" 2>/dev/null \
    | python3 -c 'import sys,json;[print(m["id"]) for m in json.load(sys.stdin)["data"]]' 2>/dev/null
}

usage() {
  cat <<EOF
Run aider against the local llama.cpp router.

  aider-local.sh list                  models the router is serving
  aider-local.sh [model] [aider args...]

Environment
  ROUTER               default $ROUTER
  AIDER_LOCAL_MODEL     default $DEFAULT_MODEL

What this sets that plain 'aider --model openai/X --openai-api-base ...'
would not, and why (full trace in aider-harness.md):

  --no-detect-urls   aider's default auto-scrapes any literal URL in any
                      message -- including one you paste in a bug report --
                      via a scraper that is broken on this box (explodes to
                      millions of tokens of context, no compaction to
                      recover). This flag is the CLI-level fix.
  --edit-format diff  qwen3.8-27B's registered default, "whole", misreads a
                      bare shell-command fence as a malformed file listing
                      and errors instead of running it. diff format does not
                      have this conflict. Harmless to force for any model.

Not fixed by this script, because there is no CLI flag for it -- only
relevant if you pass --yes-always yourself:
  --yes-always does not extend to shell commands. aider always asks
  "Run shell command?" separately, even under --yes-always, by design. In
  normal interactive use this is just a prompt you answer; it only becomes a
  problem for a fully unattended run, which needs aider-driver/'s
  monkeypatch instead of this script.

Always true, not fixable at all:
  A ```bash block is executed ONE LINE AT A TIME, not as one script -- no
  heredocs, no multi-line Python inline. Ask aider to write a script to a
  file, then run it with one single-line command (python3 script.py).
  /web is broken here even when typed manually, not just via auto-detect --
  avoid it; ask for curl instead.
EOF
}

MODEL=""; DO_LIST=0
PASS=()
SAW_FLAG=0
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)  usage; exit 0 ;;
    list)       DO_LIST=1; shift ;;
    --)         shift; while [ $# -gt 0 ]; do PASS+=("$1"); shift; done ;;
    -*)         SAW_FLAG=1; PASS+=("$1"); shift ;;
    *)          if [ -z "$MODEL" ] && [ "$SAW_FLAG" -eq 0 ]; then
                  MODEL="$1"
                else
                  PASS+=("$1")
                fi
                shift ;;
  esac
done

if [ "$DO_LIST" -eq 1 ]; then
  reachable || die "router unreachable at $ROUTER"
  echo "Models on $ROUTER:"
  models | sed 's/^/  /'
  exit 0
fi

[ -n "$MODEL" ] || MODEL="$DEFAULT_MODEL"
command -v aider >/dev/null 2>&1 || die "aider not on PATH (try: uv tool install aider-chat)"
reachable || die "router unreachable at $ROUTER -- is switch-model.sh router running on the GPU box?"

models | grep -qx "$MODEL" || {
  printf 'error: "%s" is not served by the router.\n\n' "$MODEL" >&2
  printf 'Available:\n' >&2; models | sed 's/^/  /' >&2
  exit 1
}

printf '  router  : %s\n  model   : %s\n\n' "$ROUTER" "$MODEL"

OPENAI_API_BASE="$ROUTER/v1" \
OPENAI_API_KEY="${OPENAI_API_KEY:-local}" \
exec aider --model "openai/$MODEL" --no-detect-urls --edit-format diff \
  ${PASS[@]+"${PASS[@]}"}
