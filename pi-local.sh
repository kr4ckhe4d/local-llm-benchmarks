#!/usr/bin/env bash
# Run the Pi coding agent (pi.dev) against the llama.cpp router on the LAN, or
# against Strata beside it. The Pi counterpart of claude-local.sh; runs on the
# laptop.
#
#   pi-local.sh list                     router presets and Strata
#   pi-local.sh                          default model, interactive
#   pi-local.sh qwen3.8-27B-q6-128k      pick a router preset
#   pi-local.sh strata                   Qwen3.8-Flash-Next on Strata
#   pi-local.sh strata -p "fix the bug"  anything after is passed to pi
#
# Pi's built-in llama.cpp provider lists router models only after an
# interactive /login, so this writes two providers of its own into Pi's
# models.json instead: "cachypc" (every router preset) and "strata". Other
# providers in that file are left alone. The Strata key is not written there:
# models.json gets "!cat <key file>" or "$STRATA_API_KEY", which Pi resolves per
# request.
#
# Written for macOS, so bash 3.2: no associative arrays, no ${x,,}.
set -uo pipefail

ROUTER="${ROUTER:-http://CachyPC.local:8090}"
STRATA="${STRATA:-http://CachyPC.local:8095}"
STRATA_KEY_FILE="${STRATA_KEY_FILE:-$HOME/.config/strata/api-key}"
DEFAULT_MODEL="${PI_LOCAL_MODEL:-gemma4-26B-A4B-q4-vision-128k}"
PI_DIR="${PI_CODING_AGENT_DIR:-$HOME/.pi/agent}"
PI_BIN="${PI_BIN:-pi}"

# Pi's system prompt is a few thousand tokens, not Claude Code's ~20k, so 32k
# presets are usable here.
MIN_CTX=32000

die() { printf 'error: %s\n' "$1" >&2; exit 1; }

models() {
  curl -sS --max-time 15 "$ROUTER/v1/models" 2>/dev/null \
    | python3 -c 'import sys,json;[print(m["id"]) for m in json.load(sys.stdin)["data"]]' 2>/dev/null
}

# Context is in the preset name (-32k, -128k, ...); see claude-local.sh.
ctx_of() {
  n=$(printf '%s' "$1" | grep -oE '[0-9]+k' | tail -1 | tr -d 'k')
  [ -n "$n" ] && echo $(( n * 1024 )) || echo 0
}

strata_health() { curl -sS --max-time 8 "$STRATA/health" 2>/dev/null; }
strata_ctx() {
  strata_health | python3 -c 'import sys,json;print(json.load(sys.stdin).get("max_context",0))' 2>/dev/null || echo 0
}
strata_key() {
  [ -n "${STRATA_API_KEY:-}" ] && { printf '%s' "$STRATA_API_KEY"; return; }
  [ -r "$STRATA_KEY_FILE" ] && tr -d ' \n' < "$STRATA_KEY_FILE"
}

# Strata and a router model do not fit the cards together (strata.md).
strata_unload() {
  key=$(strata_key); [ -n "$key" ] || return 0
  strata_health | grep -q '"loaded": *true' || return 0
  curl -sS --max-time 30 -o /dev/null -X POST -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $key" -d '{}' "$STRATA/v1/unload" 2>/dev/null \
    && echo "  strata  : unloaded to free the cards for $MODEL"
}

# Rewrite the "cachypc" and "strata" providers in models.json from what the
# router and Strata serve right now. Presets with "vision" in the name take
# images. maxTokens is half the context, at most 32k.
sync_models() {
  mkdir -p "$PI_DIR"
  {
    printf 'R\t%s\n' "$ROUTER"
    models | while read -r m; do
      c=$(ctx_of "$m"); [ "$c" -ge "$MIN_CTX" ] && printf 'M\t%s\t%s\n' "$m" "$c"
    done
    sc=$(strata_ctx)
    if [ "$sc" -gt 0 ]; then
      if [ -n "${STRATA_API_KEY:-}" ]; then k='$STRATA_API_KEY'; else k="!cat '$STRATA_KEY_FILE'"; fi
      printf 'S\t%s\t%s\t%s\n' "$STRATA" "$sc" "$k"
    fi
  } | python3 -c '
import sys, json, os
path = os.path.join(sys.argv[1], "models.json")
try:
    cfg = json.load(open(path))
except (OSError, ValueError):
    cfg = {}
prov = cfg.setdefault("providers", {})
prov.pop("cachypc", None); prov.pop("strata", None)
router, presets = None, []
for line in sys.stdin:
    f = line.rstrip("\n").split("\t")
    if f[0] == "R":
        router = f[1]
    elif f[0] == "M":
        ctx = int(f[2])
        presets.append({"id": f[1], "name": f[1], "reasoning": True,
                        "input": ["text", "image"] if "vision" in f[1] else ["text"],
                        "contextWindow": ctx, "maxTokens": min(32000, ctx // 2)})
    elif f[0] == "S":
        ctx = int(f[2])
        prov["strata"] = {"baseUrl": f[1] + "/v1", "api": "openai-completions", "apiKey": f[3],
                          "models": [{"id": "qwen3.8-flash-next", "name": "Qwen3.8-Flash-Next (Strata)",
                                      "reasoning": True, "input": ["text"],
                                      "contextWindow": ctx, "maxTokens": 32000}]}
if presets:
    prov["cachypc"] = {"baseUrl": router + "/v1", "api": "openai-completions", "apiKey": "local",
                       "models": presets}
tmp = path + ".tmp"
json.dump(cfg, open(tmp, "w"), indent=2)
os.replace(tmp, path)
print(len(presets), "strata" in prov)
' "$PI_DIR"
}

usage() {
  cat <<EOF
Run Pi against the local llama.cpp router, or Strata beside it.

  pi-local.sh list                  router presets and Strata
  pi-local.sh [model] [pi args...]  a router preset (default $DEFAULT_MODEL)
  pi-local.sh strata [pi args...]   Qwen3.8-Flash-Next on Strata

Environment
  ROUTER               default $ROUTER
  STRATA               default $STRATA
  STRATA_API_KEY       Strata's key; else read from $STRATA_KEY_FILE
  PI_LOCAL_MODEL       default $DEFAULT_MODEL
  PI_CODING_AGENT_DIR  Pi's agent directory (default ~/.pi/agent)
  PI_BIN               the pi command (default pi)

Notes
  * Each run rewrites the "cachypc" and "strata" providers in
    $PI_DIR/models.json; /model in Pi then lists them all.
  * A router preset first unloads Strata; Strata unloads the router model
    itself when it loads again (its before_load hook).
EOF
}

MODEL=""; DO_LIST=0; PASS=()
SAW_FLAG=0       # after the first pi flag, a bare word is that flag's value
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    list)      DO_LIST=1; shift ;;
    --)        shift; while [ $# -gt 0 ]; do PASS+=("$1"); shift; done ;;
    -*)        SAW_FLAG=1; PASS+=("$1"); shift ;;
    *)         if [ -z "$MODEL" ] && [ "$SAW_FLAG" -eq 0 ]; then MODEL="$1"; else PASS+=("$1"); fi
               shift ;;
  esac
done

command -v python3 >/dev/null 2>&1 || die "python3 not on PATH"
synced=$(sync_models) || die "could not update $PI_DIR/models.json"

if [ "$DO_LIST" -eq 1 ]; then
  echo "Router presets on $ROUTER (provider cachypc):"
  models | while read -r m; do
    c=$(ctx_of "$m"); [ "$c" -ge "$MIN_CTX" ] && printf '  %-34s %6s tok\n' "$m" "$c"
  done
  sc=$(strata_ctx)
  [ "$sc" -gt 0 ] && printf '\nStrata on %s (provider strata):\n  %-34s %6s tok\n' "$STRATA" strata "$sc"
  exit 0
fi

command -v "$PI_BIN" >/dev/null 2>&1 || die "pi not on PATH (npm install -g @earendil-works/pi-coding-agent)"
[ -n "$MODEL" ] || MODEL="$DEFAULT_MODEL"

if [ "$MODEL" = "strata" ]; then
  strata_health | grep -q '"service": *"strata"' || die "Strata unreachable at $STRATA -- is run-iq3_xxs.sh running on the GPU box?"
  [ -n "$(strata_key)" ] || die "no Strata API key: set STRATA_API_KEY or put it in $STRATA_KEY_FILE"
  PROVIDER=strata; PI_MODEL=qwen3.8-flash-next; BASE="$STRATA"
else
  models | grep -qx "$MODEL" || die "\"$MODEL\" is not served by the router at $ROUTER (pi-local.sh list)"
  [ "$(ctx_of "$MODEL")" -ge "$MIN_CTX" ] || die "$MODEL has under $MIN_CTX tokens of context"
  strata_unload
  PROVIDER=cachypc; PI_MODEL="$MODEL"; BASE="$ROUTER"
fi

printf '  server  : %s\n  model   : %s/%s\n\n' "$BASE" "$PROVIDER" "$PI_MODEL"
exec "$PI_BIN" --provider "$PROVIDER" --model "$PI_MODEL" ${PASS[@]+"${PASS[@]}"}
