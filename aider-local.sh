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
#   aider-local.sh --init                    drop CONVENTIONS.md + .aider.conf.yml into cwd
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
  aider-local.sh --init                drop CONVENTIONS.md + .aider.conf.yml
                                        into the current directory (once per
                                        project; never overwrites)
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

# Embedded rather than read from a sibling file: this script gets copied or
# symlinked to ~/.local/bin in normal use (see claude-local.sh's deployment),
# at which point a companion file left behind in the original repo would no
# longer travel with it. Keep this block in sync with CONVENTIONS.md.template
# in the repo, which exists for browsing/reference, not as a runtime dependency.
write_conventions_template() {
  cat <<'CONV'
# Conventions

Read-only file, auto-attached every session via `.aider.conf.yml`'s `read:`
key. The model sees this on every turn without it being retyped or spent out
of the context budget on repetition -- put anything here that should never
need re-explaining.

Two sections below: the first is about this **harness** (aider) and applies
to any project using it; the second is a **project** template to fill in.
Keep the harness section as-is unless something about your setup changes;
replace the project section entirely for each new codebase.

---

## Harness mechanics (aider) -- do not remove

A shell command only runs if you emit it as a fenced ```bash code block AND
include it in this same reply. Writing a script to a file is not the same as
running it -- if a task needs real output, the command to produce it belongs
in this message, not a promise to run it "next."

Each line inside a ```bash block runs as its own separate command. There is
no heredoc support and no shared state between lines -- a multi-line Python
block written directly inside a ```bash fence will be torn apart and each
line executed alone, and will fail. For anything beyond one command: write it
to a file first with a normal file edit, then run it with ONE single-line
shell command, e.g. `python3 script.py`.

Do not use the `/web` command. If it is broken in this environment, it can
consume the entire context budget on one call with no way to recover mid
session. Use `curl` for anything that needs fetching.

If a task requires seeing real output before the next step can be decided
(a computed value, a fetched file's structure, a test result), treat that as
a turn boundary -- finish this reply once the command is run, and take the
next step in a following message once you can see the result. Do not narrate
what a later step will probably show.

---

## Project: <name>

Replace this section per project. Suggested shape, delete what doesn't apply:

### Stack
- Language / framework / package manager:
- Test command:
- Lint / format command:

### Rules
- <e.g. "All new modules need a docstring">
- <e.g. "Never touch files under generated/">
- <e.g. "Prefer composition over inheritance in this codebase specifically">

### Verification discipline (recommended default -- keep unless you have a reason not to)
- Never report a check you did not run. If you did not execute something,
  say so explicitly rather than describing what it would show.
- Never invent, estimate, or normalise a number, status, or result that
  should come from a real source (a command, a file, a fetched URL). If you
  cannot obtain it, say so and stop rather than substitute a plausible value.
- When asked to verify something (tests pass, a service responds, a value is
  correct), paste the actual command output, not a summary of it.
CONV
}

init() {
  if [ -f CONVENTIONS.md ]; then
    echo "CONVENTIONS.md already exists here -- left untouched."
  else
    write_conventions_template > CONVENTIONS.md
    echo "wrote CONVENTIONS.md -- fill in the 'Project: <name>' section for this repo."
  fi

  if [ -f .aider.conf.yml ]; then
    if grep -q '^read:' .aider.conf.yml 2>/dev/null; then
      echo ".aider.conf.yml already has a 'read:' key -- left untouched."
    else
      printf 'read: CONVENTIONS.md\n' >> .aider.conf.yml
      echo "appended 'read: CONVENTIONS.md' to existing .aider.conf.yml."
    fi
  else
    printf 'read: CONVENTIONS.md\n' > .aider.conf.yml
    echo "wrote .aider.conf.yml"
  fi
}

MODEL=""; DO_LIST=0; DO_INIT=0
PASS=()
SAW_FLAG=0
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)  usage; exit 0 ;;
    list)       DO_LIST=1; shift ;;
    --init)     DO_INIT=1; shift ;;
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

if [ "$DO_INIT" -eq 1 ]; then
  init
  exit 0
fi

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
