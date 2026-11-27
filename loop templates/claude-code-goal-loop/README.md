# Claude Code goal loop: one task per session until the project is done

The [pi goal loop](../pi-goal-loop/README.md) rebuilt for **Claude Code**. It uses the same brief, task list and
handoff files, and the same guards, made from Claude Code's own parts: a shell loop around headless `claude -p` and
four hooks. Each session is a fresh `claude -p` run. It reads `CLAUDE.md` and `.ai/handoff.md`, does one task,
verifies it, commits, records it with `node tools/loop.mjs task-complete`, and exits. `run-loop.sh` then starts the
next session.

It runs against the Anthropic API or, through [`claude-local.sh`](../../claude-local.sh), against a local model on
the llama.cpp router. With the same brief and tasks as a pi run, that compares two agent harnesses on the same model.

## Quick start

```sh
"$HOME/code/local-llm-benchmarks/loop templates/claude-code-goal-loop/init.sh" ~/code/my-project --web
# fill every {{placeholder}} in CLAUDE.md, .ai/project.md, .ai/tasks.md, then:
"$HOME/code/local-llm-benchmarks/loop templates/claude-code-goal-loop/init.sh" ~/code/my-project --check
cd ~/code/my-project && git init -b main && git add -A && git commit -m "Set up Claude Code goal loop"

./run-loop.sh                                   # Anthropic API, default model
./run-loop.sh --model sonnet                    # arguments after the script go to claude
CLAUDE_BIN="$HOME/code/local-llm-benchmarks/claude-local.sh qwen3.8-27B-q6-128k" ./run-loop.sh   # local model
```

`init.sh` never overwrites existing files. No first prompt is needed: `run-loop.sh` sends the kickoff to every
session. Watch progress in the terminal, or follow `.ai/loop/runs.tsv` and `git log`. To stop, press Ctrl-C (the
loop stops after the current session ends) or `touch .ai/STOP`.

## What is in the template

| File | Role |
|---|---|
| [`CLAUDE.md`](template/CLAUDE.md) | Working rules, loaded automatically: one task per session, never ask, verify before ticking, and a fixed order to finish a task that ends with `tools/loop.mjs task-complete` |
| [`.ai/`](template/.ai/) | The brief, tasks, handoff and decision log, identical in shape to the pi template |
| [`run-loop.sh`](template/run-loop.sh) | The loop: one `claude -p` per session, logs, stop conditions |
| [`tools/loop.mjs`](template/tools/loop.mjs) | `task-complete` and `goal-complete`: Claude Code has no per-project tools, so the checks pi's extension made live here and the agent runs them with Bash |
| [`.claude/settings.json`](template/.claude/settings.json) | Registers the hooks; denies edits to the loop's own files |
| [`.claude/hooks/loop-hook.mjs`](template/.claude/hooks/loop-hook.mjs) | `SessionStart`, `PreToolUse`, `PostToolUse` and `Stop` in one script. It acts only when `LOOP_ACTIVE=1` (set by `run-loop.sh`), so opening the project interactively is unaffected |
| [`tools/shot.mjs`](template/tools/shot.mjs) | With `--web`: the headless Chrome check from the pi template |

## How it maps to the pi loop

| pi goal loop | Claude Code goal loop |
|---|---|
| `AGENTS.md` | `CLAUDE.md` |
| `task_complete` tool | `node tools/loop.mjs task-complete <id> <done\|partial> "<summary>"`. It is refused unless the handoff was rewritten this session, the tree is clean, and at most one task was newly ticked |
| `goal_complete` tool | `node tools/loop.mjs goal-complete "<evidence>"`: refused while tasks are open or the tree is dirty |
| Extension opens a new session when the run settles | `run-loop.sh` starts the next `claude -p` when the last one exits |
| Tool calls blocked after `task_complete` | `PreToolUse` hook denies every tool call once `.ai/loop/task-done` exists |
| Nudge when the run ends without `task_complete` (3 at most) | `Stop` hook blocks the stop with a nudge (3 per session at most); after that `run-loop.sh` counts the session as failed and stops after 3 failures in a row |
| 70% context warning | `PostToolUse` hook reads the last assistant message's token usage from the transcript and warns at `LOOP_CONTEXT_WARN_PCT` (70) of `LOOP_CONTEXT_WINDOW` (200,000) tokens. Set the window to the model's: 131072 for a 128K router preset |
| Loop rules in the system prompt, re-sent every 20 turns | `SessionStart` hook adds them at session start; `PostToolUse` re-sends them every `LOOP_REMIND_EVERY` (20) tool calls |
| `/loop-pause`, Esc, `.ai/STOP`, `PI_LOOP_MAX_SESSIONS` | Ctrl-C, `.ai/STOP`, `LOOP_MAX_SESSIONS` (60), `LOOP_MAX_FAILS` (3) |
| Interactive TUI only | Headless only (`claude -p`); hooks are inert outside `run-loop.sh` |

## Logs and stats

All state is under `.ai/loop/`, which is gitignored:

- `sessions/NNN.jsonl`: the full stream-json transcript of session NNN (every message, tool call, hook output), plus
  `NNN.err`.
- `runs.tsv`: one row per session: result (`T07 done`, `T07 partial`, `GOAL done`, `no task-complete`), turns,
  minutes, cost in USD (the API's figure; meaningless against a local model), input, output and cache-read tokens,
  session id.
- `loop-log.tsv`: one row per `task-complete`, like the pi loop's.

## Permissions

`run-loop.sh` passes `--permission-mode acceptEdits --allowedTools Bash Read Edit Write Glob Grep` on the command
line. The same list is in `.claude/settings.json`, but Claude Code **ignores a project's `permissions.allow` until the
folder has been trusted interactively**, and in `-p` mode anything not allowed is denied. The first smoke test of this
template failed on exactly that: every `git commit` was refused, so the model (correctly) never recorded a task. Change
the list with `LOOP_ALLOWED_TOOLS`. Inside a sandbox or VM you can pass `--dangerously-skip-permissions` instead.
`Bash` here means any shell command, so run the loop on a machine and account you are happy to give the model.

## Verified

On 2026-11-27, with Claude Haiku on a two-task toy project:

- 2 sessions: session 1 did T01 and recorded `task-complete`; `run-loop.sh` started a fresh session 2, which did T02
  and ran `goal-complete`; the loop stopped. 16 turns, 0.6 minutes, $0.02.
- The `SessionStart` context reached the model; the `Stop` hook kept a session working; with the done-marker set, a
  `PreToolUse` deny stopped a Bash call before it ran and passed the "end your turn" reason to the model.
- `tools/loop.mjs` refused: an unchanged handoff, a dirty tree, two tasks ticked in one session, a repeated
  `task-complete`, and `goal-complete` with tasks open.
- The context warning and the 20-call reminder were tested against a synthetic transcript only: a toy project never
  fills the context.

Not yet run: a full project. The [pagoda brief](../../benchmarks/pi-pagoda/loop/project.md) and
[tasks](../../benchmarks/pi-pagoda/loop/tasks.md) drop in unchanged for a pi-vs-Claude-Code comparison.
