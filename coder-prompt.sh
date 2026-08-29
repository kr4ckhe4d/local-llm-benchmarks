#!/usr/bin/env bash
# Send a properly-structured coding prompt to Qwen3-Coder-Next @ 128K.
#
# NOTE: Qwen3-Coder-Next was deleted from disk 2026-08-29 and unwired from
# switch-model.sh/models-preset.ini. This script still works — it posts to
# whatever is serving :8090 — but the system prompt and the sampling block at
# the bottom are tuned to that specific model. Re-check both against whichever
# model you point it at; thinking models in particular want a reasoning budget
# and different temperature.
#
#   ./coder-prompt.sh "add rate limiting to the /upload endpoint" src/api/*.rs
#   ./coder-prompt.sh -m 8000 "explain how auth flows through this" $(rg -l auth src/)
#
# Files listed after the task are embedded verbatim with path headers. The
# script refuses to send if the assembled prompt would not leave room for the
# reply — see the context budget note at the bottom of this file.
set -euo pipefail

HOST="${LLAMA_HOST:-http://127.0.0.1:8090}"
MAX_TOKENS=16000
CTX=131072

while getopts "m:h:" opt; do
  case $opt in
    m) MAX_TOKENS="$OPTARG" ;;
    h) HOST="$OPTARG" ;;
    *) echo "usage: $0 [-m max_tokens] [-h host] <task> [files...]" >&2; exit 1 ;;
  esac
done
shift $((OPTIND - 1))

[[ $# -ge 1 ]] || { echo "usage: $0 [-m max_tokens] [-h host] <task> [files...]" >&2; exit 1; }
TASK="$1"; shift

# --- System prompt -----------------------------------------------------------
# Qwen3-Coder-Next answers directly without a reasoning preamble. Do not ask it
# to "think step by step" — that fights the training and wastes tokens you are
# paying ~25 tok/s for.
read -r -d '' SYSTEM <<'SYS' || true
You are a senior engineer working in an existing codebase. You write code that
a colleague will read, review, and maintain.

Rules:
- Match the surrounding code. Its naming, error handling, module layout and
  comment density are the spec; your preferences are not.
- Only touch what the task requires. Do not reformat, rename, restructure or
  "improve" unrelated code.
- Output complete, runnable code. No `// ... rest unchanged`, no placeholders,
  no TODO stubs standing in for logic you were asked to write.
- Handle the error paths. Unwraps, bare excepts and ignored return values are
  defects, not brevity.
- If the task is underspecified, state the assumption you are making in one
  line and then implement it. Do not stop to ask.
- If the task cannot be done correctly as described, say so in one or two
  sentences, then implement the closest correct thing.

Output format:
- EDITING an existing file: output a unified diff in a ```diff block, with
  enough surrounding context lines to apply unambiguously. Do NOT reproduce
  the parts of the file you did not change.
- NEW file, or an existing file under ~80 lines: output it in full, in one
  fenced block, with the file path on the line immediately before the fence.
- Never print line numbers inside a code block.
- Lead with the code. Put any explanation after it, and keep it to a few lines.
- If you add a dependency, show the exact manifest line and nothing else.
SYS

# --- Assemble the context ----------------------------------------------------
CONTEXT=""
if [[ $# -gt 0 ]]; then
  # Repo map first: cheap orientation before the model reaches the bodies.
  CONTEXT+=$'## Files provided\n\n'
  for f in "$@"; do
    [[ -f "$f" ]] || { echo "warning: skipping missing file $f" >&2; continue; }
    CONTEXT+="- ${f} ($(wc -l < "$f") lines)"$'\n'
  done
  CONTEXT+=$'\n## Source\n\n'
  for f in "$@"; do
    [[ -f "$f" ]] || continue
    CONTEXT+="### ${f}"$'\n```'"${f##*.}"$'\n'
    CONTEXT+="$(cat "$f")"
    CONTEXT+=$'\n```\n\n'
  done
fi

USER_MSG="${CONTEXT}## Task

${TASK}"

# --- Budget check ------------------------------------------------------------
# ~3.5 chars/token for code is a conservative estimate (code runs denser than
# prose). Refuse rather than let the reply get truncated mid-function.
CHARS=$(( ${#SYSTEM} + ${#USER_MSG} ))
EST_TOKENS=$(( CHARS / 3 ))
BUDGET=$(( CTX - MAX_TOKENS - 2000 ))
echo "~${EST_TOKENS} input tokens (budget ${BUDGET}, reserving ${MAX_TOKENS} for output)" >&2
if (( EST_TOKENS > BUDGET )); then
  echo "ERROR: prompt too large. Send fewer files, or lower -m." >&2
  exit 1
fi

# --- Send --------------------------------------------------------------------
# Sampling per Qwen's published recommendation for Qwen3-Coder-Next:
# temp 1.0, top_p 0.95, top_k 40, min_p 0.01, repetition penalty disabled.
# These are not generic defaults — lowering temp on this model measurably
# degrades code quality.
jq -n \
  --arg sys "$SYSTEM" --arg usr "$USER_MSG" --argjson mt "$MAX_TOKENS" \
  '{
     messages: [ {role:"system", content:$sys}, {role:"user", content:$usr} ],
     temperature: 1.0, top_p: 0.95, top_k: 40, min_p: 0.01,
     repeat_penalty: 1.0, max_tokens: $mt, stream: true
   }' \
| curl -sN "$HOST/v1/chat/completions" -H 'Content-Type: application/json' -d @- \
| while IFS= read -r line; do
    [[ "$line" == data:\ * ]] || continue
    payload="${line#data: }"
    [[ "$payload" == "[DONE]" ]] && break
    # jq writes straight to stdout: command substitution would strip the
    # newlines inside each delta and collapse the whole reply onto one line.
    jq -rj '.choices[0].delta.content // empty' <<<"$payload" 2>/dev/null
  done
echo
