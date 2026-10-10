#!/usr/bin/env bash
# Run Claude Code against the llama.cpp router on the LAN instead of the
# Anthropic API. Client-side companion to switch-model.sh, which runs on the
# box with the GPU -- this one runs on the laptop.
#
#   claude-local.sh list                     what the router is serving
#   claude-local.sh                          default model, interactive
#   claude-local.sh qwen3.8-27B-q6-128k      pick a model
#   claude-local.sh --chrome                 add Chrome DevTools (text-only)
#   claude-local.sh -p "fix the bug"         anything after is passed to claude
#
# Written for macOS, so bash 3.2: no associative arrays, no ${x,,}.
set -uo pipefail

# By mDNS name, not IP: the box takes its address from DHCP, and after a
# power cut on 2026-10-06 it came back as .94 instead of .228. macOS resolves
# .local natively; the box runs avahi.
ROUTER="${ROUTER:-http://CachyPC.local:8090}"
# Gemma 4 + vision since 2026-10-06: 3.8 s warm turns, 37/50 on code-quality,
# and it can read images, so a screenshot no longer kills the session. See
# claude-harness.md, "Choosing a model".
DEFAULT_MODEL="${CLAUDE_LOCAL_MODEL:-gemma4-26B-A4B-q4-vision-128k}"

# SearXNG on the Proxmox box, for web search from local models. Its JSON API
# (format=json) is enabled; a stock SearXNG answers 403 there.
SEARXNG_URL="${SEARXNG_URL:-http://192.168.5.33:8080}"

# Strata (Qwen3.8-Flash-Next IQ3_XXS) runs beside the router, not in it: the
# router can only spawn llama-server. `claude-local.sh strata` talks to it
# directly. It needs an API key because it listens on the LAN; copy it from
# ~/code/Strata/.strata-api-key on the box. See strata.md.
STRATA="${STRATA:-http://CachyPC.local:8095}"
STRATA_KEY_FILE="${STRATA_KEY_FILE:-$HOME/.config/strata/api-key}"

# Claude Code's system prompt measured 41,796 tokens on 2026-08-23 with the
# claude.ai connectors attached, 24-27k without, and ~20k on 2.1.290 (2026-10-06;
# Muse's tokenizer doubles it). A 32k preset has too little left for a real
# task, so 64k is the smallest bucket offered.
MIN_CTX=64000

# Only take_screenshot returns an image; a text-only model 500s on image input
# ("image input is not supported") and Claude Code retry-loops on it. So it is
# left out unless the preset has a vision projector (name contains "vision"),
# which reads screenshots fine. take_snapshot is the text replacement.
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

# Context is encoded in the preset name: ...-32k, -128k, -200k, -256k. Take the
# last such group rather than anchoring at end-of-string, so suffixed presets
# like qwen3.8-27B-16k-mtp report 16k instead of falling through to zero.
ctx_of() {
  n=$(printf '%s' "$1" | grep -oE '[0-9]+k' | tail -1 | tr -d 'k')
  [ -n "$n" ] && echo $(( n * 1024 )) || echo 0
}

# Presets Claude Code can actually use. Anything under MIN_CTX cannot answer a
# single request -- the system prompt alone overflows it -- so listing them as
# choices is just offering a guaranteed error. --any-ctx brings them back.
usable() {
  models | while read -r m; do
    [ "$(ctx_of "$m")" -ge "$MIN_CTX" ] && echo "$m"
  done
}
listable() { [ "$ANY_CTX" -eq 1 ] && models || usable; }

strata_key() {
  [ -n "${STRATA_API_KEY:-}" ] && { printf '%s' "$STRATA_API_KEY"; return; }
  [ -r "$STRATA_KEY_FILE" ] && tr -d ' \n' < "$STRATA_KEY_FILE"
}

# /health needs no key: {"max_context": 204800, "loaded": true, "service": "strata", ...}
strata_health() { curl -sS --max-time 8 "$STRATA/health" 2>/dev/null; }
strata_ctx() {
  strata_health | python3 -c 'import sys,json;print(json.load(sys.stdin).get("max_context",0))' 2>/dev/null || echo 0
}

# Strata and a router model do not fit the cards together. Before a router
# model, ask Strata to give the VRAM back (it reloads on its next request, and
# its before_load hook unloads the router model then).
strata_unload() {
  key=$(strata_key); [ -n "$key" ] || return 0
  strata_health | grep -q '"loaded": *true' || return 0
  curl -sS --max-time 30 -o /dev/null -X POST -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $key" -d '{}' "$STRATA/v1/unload" 2>/dev/null \
    && echo "  strata  : unloaded to free the cards for $MODEL"
}

usage() {
  cat <<EOF
Run Claude Code against the local llama.cpp router.

  claude-local.sh list                 models the router is serving
  claude-local.sh [model] [claude args...]
  claude-local.sh strata [claude args...]   Qwen3.8-Flash-Next on Strata (port 8095)

Options
  --chrome        enable Chrome DevTools MCP (text-only tools; no screenshots)
  --no-search     do not attach SearXNG web search
  --any-ctx       allow presets under ${MIN_CTX} tokens (they will fail; for testing)
  -h, --help      this

Environment
  ROUTER               default $ROUTER
  CLAUDE_LOCAL_MODEL   default $DEFAULT_MODEL
  SEARXNG_URL          default $SEARXNG_URL
  STRATA               default $STRATA
  STRATA_API_KEY       Strata's key; else read from $STRATA_KEY_FILE

Notes
  * Claude Code's system prompt is ~20k tokens, so only 64k+ presets are offered.
  * On presets without "vision" in the name, Read on image files is denied:
    one image in context 500s every later request on a text-only model.
  * Web search goes through SearXNG (mcp-searxng, needs npx); Claude Code's
    own WebSearch runs on Anthropic's servers and is denied here.
  * No other MCP servers unless --chrome: three Notion connector schemas
    crash llama.cpp's grammar compiler ("failed to parse grammar"), which
    breaks tool calling entirely.
  * All four model slots (main/sonnet/opus/haiku) are pinned to one model --
    the router is --models-max 1, so a second model would evict the first.
EOF
}

MODEL=""; USE_CHROME=0; USE_SEARCH=1; ANY_CTX=0; DO_LIST=0
PASS=()          # everything destined for claude, kept as distinct words
SAW_FLAG=0       # after the first claude flag, stop treating bare words as a model
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)  usage; exit 0 ;;
    list)       DO_LIST=1; shift ;;
    --chrome)   USE_CHROME=1; shift ;;
    --no-search) USE_SEARCH=0; shift ;;
    --any-ctx)  ANY_CTX=1; shift ;;
    --)         shift; while [ $# -gt 0 ]; do PASS+=("$1"); shift; done ;;
    -*)         SAW_FLAG=1; PASS+=("$1"); shift ;;
    *)          # The first bare word before any claude flag is the model. Do
                # not pattern-match the name -- presets like qwen3.8-27B-16k-mtp
                # do not end in <n>k and were silently falling through to the
                # default. It is validated against the router's list below.
                # After a flag, a bare word is that flag's value (the prompt
                # after -p) and must pass through as one word.
                if [ -z "$MODEL" ] && [ "$SAW_FLAG" -eq 0 ]; then
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
  listable | while read -r m; do printf '  %-34s %6s tok\n' "$m" "$(ctx_of "$m")"; done
  if [ "$ANY_CTX" -eq 0 ]; then
    hidden=$(( $(models | wc -l) - $(usable | wc -l) ))
    [ "$hidden" -gt 0 ] && printf '\n  %s preset(s) under %s tokens hidden -- too small for Claude Code (--any-ctx to show)\n' \
      "$hidden" "$MIN_CTX"
  fi
  sctx=$(strata_ctx)
  [ "$sctx" -gt 0 ] && printf '\nBeside the router, on %s:\n  %-34s %6s tok\n' "$STRATA" strata "$sctx"
  exit 0
fi

[ -n "$MODEL" ] || MODEL="$DEFAULT_MODEL"

# Strata replaces the router for this session: its own URL, key and context.
BASE="$ROUTER"; TOKEN="${ANTHROPIC_AUTH_TOKEN:-local}"
if [ "$MODEL" = "strata" ]; then
  command -v claude >/dev/null 2>&1 || die "claude not on PATH (try: export PATH=\"\$HOME/.local/bin:\$PATH\")"
  strata_health | grep -q '"service": *"strata"' || die "Strata unreachable at $STRATA -- is run-iq3_xxs.sh running on the GPU box?"
  TOKEN=$(strata_key)
  [ -n "$TOKEN" ] || die "no Strata API key: set STRATA_API_KEY or put it in $STRATA_KEY_FILE"
  BASE="$STRATA"
  CTX=$(strata_ctx)
else
  command -v claude >/dev/null 2>&1 || die "claude not on PATH (try: export PATH=\"\$HOME/.local/bin:\$PATH\")"
  reachable || die "router unreachable at $ROUTER -- is switch-model.sh router running on the GPU box?"

  models | grep -qx "$MODEL" || {
    printf 'error: "%s" is not served by the router.\n\n' "$MODEL" >&2
    printf 'Available:\n' >&2; listable | sed 's/^/  /' >&2
    exit 1
  }

  CTX=$(ctx_of "$MODEL")
  strata_unload
fi
if [ "$CTX" -lt "$MIN_CTX" ] && [ "$ANY_CTX" -eq 0 ]; then
  die "$MODEL has only $CTX tokens; Claude Code's system prompt alone is ~42k.
       Pick a 128k or 256k preset, or pass --any-ctx to try anyway."
fi

# MCP: SearXNG (unless --no-search) and chrome-devtools (with --chrome). Never
# the account connectors -- see the Notion grammar note in usage().
TMP="$(mktemp -d "${TMPDIR:-/tmp}/claude-local.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
SERVERS=""; TOOLS=""
DENY=""          # one --disallowedTools list; a second flag would not merge
add_server() { SERVERS="${SERVERS:+$SERVERS,}$1"; }
allow() { TOOLS="${TOOLS:+$TOOLS,}$1"; }
deny()  { DENY="${DENY:+$DENY,}$1"; }

# Web search through SearXNG, added 2026-10-06. Claude Code's own WebSearch is
# a server tool that runs on Anthropic's side, so against llama.cpp it has
# nothing to run on; it is denied whenever SearXNG is attached, so the model
# reaches for the one that works. mcp-searxng is pinned: its four tool schemas
# were checked against llama.cpp's grammar compiler at this version.
if [ "$USE_SEARCH" -eq 1 ] && command -v npx >/dev/null 2>&1; then
  add_server "\"searxng\":{\"command\":\"npx\",\"args\":[\"-y\",\"mcp-searxng@2.5.0\"],\"env\":{\"SEARXNG_URL\":\"$SEARXNG_URL\"}}"
  allow "mcp__searxng__searxng_web_search,mcp__searxng__searxng_search_suggestions,mcp__searxng__searxng_instance_info,mcp__searxng__web_url_read"
  deny "WebSearch"
  SEARCH_NOTE="  search  : SearXNG at $SEARXNG_URL (--no-search to disable)"
elif [ "$USE_SEARCH" -eq 1 ]; then
  SEARCH_NOTE="  search  : off -- SearXNG needs npx (install Node)"
else
  SEARCH_NOTE="  search  : off (--no-search)"
fi

if [ "$USE_CHROME" -eq 1 ]; then
  command -v npx >/dev/null 2>&1 || die "--chrome needs npx (install Node)"
  add_server '"chrome-devtools":{"command":"npx","args":["-y","chrome-devtools-mcp@latest","--isolated"]}'
  allow "$CHROME_SAFE"
  case "$MODEL" in
    *vision*) allow "mcp__chrome-devtools__take_screenshot"
              EXTRA_NOTE="  chrome  : on (vision preset: screenshots allowed)" ;;
    *)        EXTRA_NOTE="  chrome  : on (text-only tools; take_snapshot instead of screenshots)" ;;
  esac
else
  EXTRA_NOTE="  chrome  : off (--chrome to enable)"
fi

printf '{"mcpServers":{%s}}' "$SERVERS" > "$TMP/mcp.json"
ARGS=(--strict-mcp-config --mcp-config "$TMP/mcp.json")
[ -n "$TOOLS" ] && ARGS+=(--allowedTools "$TOOLS")

# Read sends an image too when pointed at one, and on a text-only preset that
# is the same 500 and retry loop as a screenshot (claude-harness.md, Gotcha 4).
# On 2026-10-06 Qwen3.8 read its own WebGL screenshot mid-task and the session
# was dead: the image stays in context, so every later request fails as well.
# Deny the image files outright rather than ask the model not to. The leading
# // makes the pattern absolute; a bare **/*.png only covers the working
# directory, and that screenshot was in /tmp.
case "$MODEL" in
  *vision*) IMG_NOTE="  images  : allowed (vision preset)" ;;
  *)        for ext in png jpg jpeg gif webp bmp PNG JPG JPEG GIF WEBP BMP; do
              deny "Read(//**/*.$ext)"
            done
            IMG_NOTE="  images  : Read on image files denied (text-only preset)" ;;
esac
[ -n "$DENY" ] && ARGS+=(--disallowedTools "$DENY")

printf '  server  : %s\n  model   : %s\n  context : %s tokens\n%s\n%s\n%s\n\n' \
  "$BASE" "$MODEL" "$CTX" "$SEARCH_NOTE" "$EXTRA_NOTE" "$IMG_NOTE"

# All four slots on one model. Unset slots fall back to real Anthropic names
# and 400 with "model 'claude-sonnet-5' not found".
ANTHROPIC_BASE_URL="$BASE" \
ANTHROPIC_AUTH_TOKEN="$TOKEN" \
ANTHROPIC_MODEL="$MODEL" \
ANTHROPIC_DEFAULT_SONNET_MODEL="$MODEL" \
ANTHROPIC_DEFAULT_OPUS_MODEL="$MODEL" \
ANTHROPIC_DEFAULT_HAIKU_MODEL="$MODEL" \
ANTHROPIC_SMALL_FAST_MODEL="$MODEL" \
CLAUDE_CODE_MAX_CONTEXT_TOKENS="$CTX" \
exec claude "${ARGS[@]}" ${PASS[@]+"${PASS[@]}"}
