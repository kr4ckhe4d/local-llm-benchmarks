# pi goal loop: let a local model work unattended until a project is done

A template that makes the [Pi](https://pi.dev) coding agent work through a project on its own, **one task per
session**, until every acceptance check passes. Each session starts fresh, reads a handoff file the previous
session wrote, does one task, verifies it, commits, and hands off. Nobody needs to answer questions or review code
during the run.

It is what built the [pagoda garden](../../pi-pagoda-demo.md): Qwen3.8-27B Q8_0 on this machine's llama.cpp router,
16 tasks, 21 sessions, 11.8 hours unattended. The loop failures in that run (below) are fixed in this version of
the template.

## Quick start

```sh
"$HOME/code/local-llm-benchmarks/loop templates/pi-goal-loop/init.sh" ~/code/my-project --web   # --web adds tools/shot.mjs
# fill every {{placeholder}} in AGENTS.md, .ai/project.md, .ai/tasks.md
"$HOME/code/local-llm-benchmarks/loop templates/pi-goal-loop/init.sh" ~/code/my-project --check # must print OK
cd ~/code/my-project && git init -b main && git add -A && git commit -m "Set up pi goal loop"
pi -a --model cachypc/qwen3.8-27B-q8-128k     # -a trusts the folder, so the extension loads
```

`init.sh` never overwrites files that already exist. Then send this as the first prompt; the loop sends the same
text to every new session:

```
Continue the project loop. Read AGENTS.md, then .ai/handoff.md, then the files it points to. Pick the next task as AGENTS.md describes and work until it meets its done-criteria. Do not stop to ask me questions.
```

The loop only runs in Pi's interactive terminal UI. With `pi -p` (print mode) the extension stays inactive, so a
scripted run exits normally.

## What is in the template

| File | Role |
|---|---|
| [`AGENTS.md`](template/AGENTS.md) | Working rules. Pi loads it automatically. One task per session, never ask questions (decide and log it), verify before ticking, and a fixed order to finish a task: verify, tick, rewrite the handoff, commit, call `task_complete` |
| [`.ai/project.md`](template/.ai/project.md) | The brief: goal, required contents, test contract, **measurable acceptance checks**, a 1-5 quality rubric with a description of what a 5 looks like |
| [`.ai/tasks.md`](template/.ai/tasks.md) | Ordered tasks, each one session long, each with a **Done when** line. T01 is a scaffold that makes the check command pass; the last task is a final review that ends with `goal_complete` |
| [`.ai/handoff.md`](template/.ai/handoff.md) | Rewritten (not appended) at the end of every task: current state, measured numbers, rubric scores, **gotchas carried forward**, known problems, the exact next step. The next session's only memory |
| [`.ai/decisions.md`](template/.ai/decisions.md) | Append-only log of every call the agent made on its own, one line each with a reason |
| [`.pi/extensions/goal-loop.ts`](template/.pi/extensions/goal-loop.ts) | The loop itself (below) |
| [`tools/shot.mjs`](template/tools/shot.mjs) | With `--web`: headless Chrome on the real GPU for browser projects (below) |
| [`gitignore`](template/gitignore) | Installed as `.gitignore`: screenshots, the loop log, the stop file |

## How the loop works

The extension adds two tools and three commands to Pi:

- **`task_complete(task_id, status, summary)`** is refused unless `.ai/handoff.md` was rewritten in this session
  and the git tree is clean. It is also refused if more than one task was newly ticked `[x]` in the session. Once
  accepted, the entry is written to `.ai/loop-log.tsv`. When the run ends, the extension opens a **new session** and
  sends the kickoff prompt.
- **`goal_complete(evidence)`** is refused while any task is still `[ ]` or `[~]` or the tree is dirty. When
  accepted, it writes `.ai/GOAL_MET` and stops the loop.
- `/loop-next` forces a new session, `/loop-resume` continues after you pressed Esc, `/loop-pause` stops automatic
  continuation. `touch .ai/STOP` stops it from the shell. `PI_LOOP_MAX_SESSIONS` (default 60) caps how many sessions
  the loop will start.

Guards that keep a long run on track:

| Guard | Why it exists |
|---|---|
| Every tool call after `task_complete` is blocked with `terminate`, which forces the run to end | In the pagoda run's T06 the model ignored "end your turn": it kept working in the same run for 80 more minutes, compacted twice, then wrote "A new session has started…" and began the next task at 80% context. The new session never started because the run never ended |
| Repeat `task_complete` calls are blocked too | In T12 a repetition loop called `task_complete` 15 times in 2 minutes |
| At 70% context the agent is told to hand off the task as `partial` | The warning fired in 8 of 16 pagoda tasks; 5 were handed off as `partial` and finished by a later session |
| The loop rules are added to every system prompt and re-sent every 20 turns | Long sessions push AGENTS.md far back in the context |
| If a run ends without `task_complete`, the agent is nudged to continue, at most 3 times in a row | Models stop to ask questions or summarise |
| Esc pauses the loop instead of fighting you | So you can step in |

## Verification is the whole game

The loop only works as well as the check the agent runs on itself. For browser projects, `tools/shot.mjs`:

- serves the repo root, opens each view from `tools/views.json` in headless Chrome on the GPU (Vulkan, so FPS is
  real), and saves `shots/<name>.png`;
- reports console errors, page errors and failed requests (exit 1 on any), FPS, the page's own `window.__diag`
  object, and **image statistics** for models that cannot look at a PNG: mean brightness, black and blown-out pixel
  shares, edge density, distinct colours, dominant hues;
- runs in-page probes with `--eval "<expr>"` or `--eval-file probe.js` (an async function body: multi-line code,
  comments and `await` all work).

For other kinds of project, put a test suite, benchmark script or CLI check in its place and name it in AGENTS.md.

**Pick a model that can see images when quality is visual.** `pi --list-models` shows which models accept images.
Qwen3.8-27B cannot. It judged the pagoda scene from statistics alone, which caught exposure, colour, missing objects
and two real three.js bugs, but not shape or orientation. Its koi rendered as black shapes (no vertex normals) while
it scored its own realism 4 of 5. AGENTS.md tells a text-only model to say in the handoff that its review was
stats-only.

## Writing the brief

- **Acceptance checks must be numbers or exit codes** ("`shot.mjs --all` exits 0, FPS >= 55 in every view, draw
  calls < 600"), never "looks good". The agent will call `goal_complete` against them.
- **Describe what a 5 looks like** for each rubric line. The model will score itself against it.
- **Size tasks to one session**, about half the model's context of work, and aim for 10-20 tasks. The agent may split
  a task (T05 into T05a and T05b) if it turns out too big.
- **Give it a test contract.** The pagoda page exposed `window.__diag` (draw calls, triangles, frame time, object
  counts). The check tool reads it, so "the koi exist" is a number rather than a guess.
- **Write down the environment**: OS, GPU, network policy, how a human previews the result.
- Keep secrets out of `.ai/`: it is committed.

## Running a comparison

To compare models, keep `.ai/project.md` and `.ai/tasks.md` byte-identical across folders and change only the model
on the `pi` command line. `benchmarks/pi-pagoda/collect.py` recomputes wall clock, sessions, tool calls, tokens and
per-task minutes from Pi's session files (`~/.pi/agent/sessions/`) and the loop log. Two `task_complete` entries
inside one session file mean the rollover did not happen.

The same template is also packaged as a Claude Code skill (`pi-goal-loop`), which fills in the brief and tasks
from a one-line request.
