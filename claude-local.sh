#!/usr/bin/env bash
# Run Claude Code against the llama.cpp router on the LAN instead of the
# Anthropic API. Client-side companion to switch-model.sh, which runs on the
# box with the GPU -- this one runs on the laptop.
#
#   claude-local.sh list                     what the router is serving
#   claude-local.sh                          default model, interactive
#   claude-local.sh qwen3-coder-80B-A3B-128k pick a model
#   claude-local.sh --chrome                 add Chrome DevTools (text-only)
#   claude-local.sh -p "fix the bug"         anything after is passed to claude
#
# Written for macOS, so bash 3.2: no associative arrays, no ${x,,}.
set -uo pipefail

ROUTER="${ROUTER:-http://192.168.4.228:8090}"
DEFAULT_MODEL="${CLAUDE_LOCAL_MODEL:-laguna-33B-A3B-q8-128k}"

# Claude Code's system prompt measured 41,796 tokens on 2026-08-23. A preset
# below this cannot answer at all -- it fails on the first request with
# "exceeds the available context size". 64k is the smallest safe bucket.
MIN_CTX=64000

# Only take_screenshot returns an image; a text-only model 500s on image input
# ("image input is not supported"). Everything else here returns text.
# take_snapshot is the screenshot replacement -- accessibility tree, as text.
CHROME_SAFE="mcp__chrome-devtools__click,mcp__chrome-devtools__close_page,\
mcp__chrome-devtools__evaluate_script,mcp__chrome-devtools__fill,\
mcp__chrome-devtools__fill_form,mcp__chrome-devtools__get_console_message,\
mcp__chrome-devtools__get_network_request,mcp__chrome-devtools__handle_dialog,\
mcp__chrome-devtools__hover,mcp__chrome-devtools__list_console_messages,\
mcp__chrome-devtools__list_network_requests,mcp__chrome-devtools__list_pages,\
mcp__chrome-devtools__navigate_page,mcp__chrome-devtools__new_page,\
mcp__chrome-devtools__press_key,mcp__chrome-devtools__resize_page,\
mcp__chrome-devtools__select_page,mcp__chrome-devtools__take_snapshot,\
mcp__chrome-devtools__type_text,mcp__chrome-devtools__wait_for"

die() { printf 'error: %s\n' "$1" >&2; exit 1; }

reachable() {
  curl -sS --max-time 8 -o /dev/null "$ROUTER/v1/models" 2>/dev/null
}

models() {
  curl -sS --max-time 15 "$ROUTER/v1/models" 2>/dev/null \
    | python3 -c 'import sys,json;[print(m["id"]) for m in json.load(sys.stdin)["data"]]' 2>/dev/null
}

# Context is encoded in the preset name: ...-32k, -128k, -200k, -256k.
ctx_of() {
  n=$(printf '%s' "$1" | grep -oE '[0-9]+k$' | tr -d 'k')
  [ -n "$n" ] && echo $(( n * 1024 )) || echo 0
}

usage() {
  cat <<EOF
Run Claude Code against the local llama.cpp router.

  claude-local.sh list                 models the router is serving
  claude-local.sh [model] [claude args...]

Options
  --chrome        enable Chrome DevTools MCP (text-only tools; no screenshots)
  --any-ctx       allow presets under ${MIN_CTX} tokens (they will fail; for testing)
  -h, --help      this

Environment
  ROUTER               default $ROUTER
  CLAUDE_LOCAL_MODEL   default $DEFAULT_MODEL

Notes
  * Claude Code's system prompt is ~42k tokens, so 32k presets cannot work.
  * MCP servers are disabled unless --chrome: three Notion connector schemas
    crash llama.cpp's grammar compiler ("failed to parse grammar"), which
    breaks tool calling entirely.
  * All four model slots (main/sonnet/opus/haiku) are pinned to one model --
    the router is --models-max 1, so a second model would evict the first.
EOF
}

MODEL=""; USE_CHROME=0; ANY_CTX=0
PASS=()          # everything destined for claude, kept as distinct words
SAW_FLAG=0       # after the first claude flag, stop treating bare words as a model
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)  usage; exit 0 ;;
    list)       reachable || die "router unreachable at $ROUTER"
                echo "Models on $ROUTER:"
                models | while read -r m; do
                  c=$(ctx_of "$m")
                  if [ "$c" -ge "$MIN_CTX" ]; then printf '  %-34s %6s tok\n' "$m" "$c"
                  else                             printf '  %-34s %6s tok  (too small for Claude Code)\n' "$m" "$c"; fi
                done
                exit 0 ;;
    --chrome)   USE_CHROME=1; shift ;;
    --any-ctx)  ANY_CTX=1; shift ;;
    --)         shift; while [ $# -gt 0 ]; do PASS+=("$1"); shift; done ;;
    -*)         SAW_FLAG=1; PASS+=("$1"); shift ;;
    *)          # A bare word is the model only if it looks like a preset AND we
                # have not yet seen a claude flag -- otherwise it is that flag's
                # value (e.g. the prompt after -p) and must be passed through
                # as a single word.
                if [ -z "$MODEL" ] && [ "$SAW_FLAG" -eq 0 ] && printf '%s' "$1" | grep -qE '[0-9]+k$'; then
                  MODEL="$1"
                else
                  PASS+=("$1")
                fi
                shift ;;
  esac
done

[ -n "$MODEL" ] || MODEL="$DEFAULT_MODEL"
command -v claude >/dev/null 2>&1 || die "claude not on PATH (try: export PATH=\"\$HOME/.local/bin:\$PATH\")"
reachable || die "router unreachable at $ROUTER -- is switch-model.sh router running on the GPU box?"

models | grep -qx "$MODEL" || {
  printf 'error: "%s" is not served by the router.\n\n' "$MODEL" >&2
  printf 'Available:\n' >&2; models | sed 's/^/  /' >&2
  exit 1
}

CTX=$(ctx_of "$MODEL")
if [ "$CTX" -lt "$MIN_CTX" ] && [ "$ANY_CTX" -eq 0 ]; then
  die "$MODEL has only $CTX tokens; Claude Code's system prompt alone is ~42k.
       Pick a 128k or 256k preset, or pass --any-ctx to try anyway."
fi

# MCP: nothing at all, or chrome-devtools only. Never the account connectors --
# see the Notion grammar note in usage().
TMP="$(mktemp -d "${TMPDIR:-/tmp}/claude-local.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
if [ "$USE_CHROME" -eq 1 ]; then
  command -v npx >/dev/null 2>&1 || die "--chrome needs npx (install Node)"
  cat > "$TMP/mcp.json" <<'JSON'
{"mcpServers":{"chrome-devtools":{"command":"npx","args":["-y","chrome-devtools-mcp@latest","--isolated"]}}}
JSON
  ARGS=(--strict-mcp-config --mcp-config "$TMP/mcp.json" --allowedTools "$CHROME_SAFE")
  EXTRA_NOTE="  chrome  : on (text-only tools; take_snapshot instead of screenshots)"
else
  printf '{"mcpServers":{}}' > "$TMP/mcp.json"
  ARGS=(--strict-mcp-config --mcp-config "$TMP/mcp.json")
  EXTRA_NOTE="  chrome  : off (--chrome to enable)"
fi

printf '  router  : %s\n  model   : %s\n  context : %s tokens\n%s\n\n' \
  "$ROUTER" "$MODEL" "$CTX" "$EXTRA_NOTE"

# All four slots on one model. Unset slots fall back to real Anthropic names
# and 400 with "model 'claude-sonnet-5' not found".
ANTHROPIC_BASE_URL="$ROUTER" \
ANTHROPIC_AUTH_TOKEN="${ANTHROPIC_AUTH_TOKEN:-local}" \
ANTHROPIC_MODEL="$MODEL" \
ANTHROPIC_DEFAULT_SONNET_MODEL="$MODEL" \
ANTHROPIC_DEFAULT_OPUS_MODEL="$MODEL" \
ANTHROPIC_DEFAULT_HAIKU_MODEL="$MODEL" \
ANTHROPIC_SMALL_FAST_MODEL="$MODEL" \
CLAUDE_CODE_MAX_CONTEXT_TOKENS="$CTX" \
exec claude "${ARGS[@]}" ${PASS[@]+"${PASS[@]}"}
