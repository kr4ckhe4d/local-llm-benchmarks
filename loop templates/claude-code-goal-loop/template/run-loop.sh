#!/usr/bin/env bash
# Run Claude Code on this project, one task per session, until .ai/GOAL_MET exists.
#
#   ./run-loop.sh                          the Anthropic API, default model
#   ./run-loop.sh --model sonnet           anything after the script name is passed to claude
#   CLAUDE_BIN="$HOME/code/local-llm-benchmarks/claude-local.sh qwen3.8-27B-q6-128k" ./run-loop.sh
#                                          a local model through the llama.cpp router
#
# Each session is a fresh `claude -p` run: it reads CLAUDE.md and .ai/handoff.md, does one task, commits, and runs
# `node tools/loop.mjs task-complete`. The hooks in .claude/ (active only under this script) block tool calls after
# that, nudge a session that tries to stop early, and warn at 70% context. Stops when:
#   .ai/GOAL_MET exists (goal-complete ran), .ai/STOP exists (touch it to stop after the current session),
#   LOOP_MAX_SESSIONS (60) sessions ran, or LOOP_MAX_FAILS (3) sessions in a row ended without task-complete.
# Logs: .ai/loop/sessions/NNN.jsonl (stream-json transcript), .ai/loop/runs.tsv (one line per session),
#       .ai/loop/loop-log.tsv (one line per task-complete).
set -uo pipefail
cd "$(dirname "$0")"

KICKOFF="Continue the project loop. Read CLAUDE.md, then .ai/handoff.md, then the files it points to. Pick the next task as CLAUDE.md describes and work until it meets its done-criteria. Do not stop to ask questions."
read -r -a CLAUDE_CMD <<< "${CLAUDE_BIN:-claude}"
# Permissions go on the command line: Claude Code ignores permissions.allow in .claude/settings.json until the
# folder has been trusted interactively, and in -p mode anything not allowed is denied (git commit included).
# Override with LOOP_ALLOWED_TOOLS, or pass e.g. --dangerously-skip-permissions inside a sandbox.
read -r -a ALLOWED <<< "${LOOP_ALLOWED_TOOLS:-Bash Read Edit Write Glob Grep}"
MAX=${LOOP_MAX_SESSIONS:-60}
MAX_FAILS=${LOOP_MAX_FAILS:-3}
LOOP=.ai/loop
mkdir -p "$LOOP/sessions"
[ -f "$LOOP/runs.tsv" ] || printf 'n\tstart\tend\tresult\tturns\tminutes\tcost_usd\tinput\toutput\tcache_read\tsession_id\n' > "$LOOP/runs.tsv"

stopping=0
trap 'echo; echo "run-loop: interrupted, stopping after this session"; stopping=1' INT

fails=0
while :; do
  [ -f .ai/GOAL_MET ] && { echo "run-loop: goal met"; exit 0; }
  [ -f .ai/STOP ] && { echo "run-loop: .ai/STOP found, stopping"; exit 0; }
  [ $stopping = 1 ] && exit 130
  n=$(( $(find "$LOOP/sessions" -name '*.jsonl' | wc -l) + 1 ))
  [ "$n" -gt "$MAX" ] && { echo "run-loop: LOOP_MAX_SESSIONS=$MAX reached"; exit 1; }
  log=$(printf '%s/sessions/%03d' "$LOOP" "$n")

  # session snapshot for tools/loop.mjs: start time (handoff must be newer) and tasks already ticked
  rm -f "$LOOP/task-done"
  node -e '
    const fs = require("fs"); const ids = [];
    try { for (const l of fs.readFileSync(".ai/tasks.md", "utf8").split("\n")) { const m = l.match(/^\s*- \[x\]\s*\**\s*([A-Za-z]*\d+[a-z]?)/i); if (m) ids.push(m[1]); } } catch {}
    fs.writeFileSync(".ai/loop/session.json", JSON.stringify({ n: +process.argv[1], start: Date.now(), done: ids }));' "$n"

  start=$(date -u +%FT%TZ)
  echo "run-loop: session $n started $start"
  LOOP_ACTIVE=1 "${CLAUDE_CMD[@]}" -p "$KICKOFF" --output-format stream-json --verbose \
    --permission-mode acceptEdits --allowedTools "${ALLOWED[@]}" "$@" > "$log.jsonl" 2> "$log.err" < /dev/null
  rc=$?

  # one line of stats from the final "result" event
  node -e '
    const fs = require("fs"); const [log, n, start, rc] = process.argv.slice(1);
    let r = null; for (const l of fs.readFileSync(log, "utf8").trim().split("\n")) { try { const e = JSON.parse(l); if (e.type === "result") r = e; } catch {} }
    const done = fs.existsSync(".ai/loop/task-done") ? fs.readFileSync(".ai/loop/task-done", "utf8").trim().replace("\t", " ") : (r ? "no task-complete" : "no result (exit " + rc + ")");
    const u = r?.usage || {};
    const row = [n, start, new Date().toISOString().slice(0, 19) + "Z", done, r?.num_turns ?? "", r ? (r.duration_ms / 60000).toFixed(1) : "",
      r?.total_cost_usd ?? "", u.input_tokens ?? "", u.output_tokens ?? "", u.cache_read_input_tokens ?? "", r?.session_id ?? ""];
    fs.appendFileSync(".ai/loop/runs.tsv", row.join("\t") + "\n");
    console.log(`run-loop: session ${n}: ${done}, ${row[4] || "?"} turns, ${row[5] || "?"} min`);' "$log.jsonl" "$n" "$start" "$rc"

  if [ -f "$LOOP/task-done" ]; then
    fails=0
  else
    fails=$((fails + 1))
    echo "run-loop: session $n ended without task-complete ($fails in a row); see $log.err"
    [ "$fails" -ge "$MAX_FAILS" ] && { echo "run-loop: $MAX_FAILS sessions in a row without task-complete, stopping"; exit 1; }
  fi
done
