# Claude Code project template for local models

Starter files for building a project with Claude Code against the local
llama.cpp router (`claude-local.sh`). Distilled from the 2026-10-08
`gemma31-q6-claude-code` project, where this layout let KAT-Coder-V2.5 work
task by task through subagents while Gemma 4 31B, in a single long chat,
stalled (claude-harness.md).

## What gets generated

| File | Role | Size target |
|---|---|---|
| `CLAUDE.md` | Loaded on every turn **and by every subagent**: constraints, commands, the working protocol, a spec index | under ~8 KB |
| `docs/<topic>.md` | The detailed spec, split by topic, read only when a task needs it | under ~8 KB each |
| `PLAN.md` | Ordered tasks, each one subagent run, tagged with the docs to read | |
| `scripts/progress.mjs` | **The only writer** of PLAN.md ticks, `progress/` and PROGRESS.md (`done`, `note`, `resolve`, `decision`, `check`) | copied as is |
| `scripts/smoke.mjs` | Runtime smoke test for a built static site: headless Chrome at desktop/phone, reduced motion, no JS; prints each unique problem once as text (exceptions, 404s, hidden content, contrast, fixed/overflow) | copied as is (web projects) |
| `progress/` | One file per finished task (written once), plus `decisions.md` and `notes.md` | |
| `PROGRESS.md` | **Generated** view: Next (computed from PLAN.md), open notes, decisions, recent log | stays short |
| `.claude/agents/implementer.md` | Does one PLAN task, replies in 15 lines | |
| `.claude/agents/test-runner.md` | Runs the checks, reports pass/fail only | |

`CLAUDE.md.template` and `PLAN.md.template` have `{{PLACEHOLDERS}}`. The two
agent files are generic and only need the check commands filled in.
`scripts/progress.mjs` is copied unchanged; PLAN.md task lines must keep the
`- [ ] <id> <title>` form it parses.

## How to generate from a feature brief

Given the user's description of what to build:

1. **Pick the stack and the check commands** (typecheck, lint, test, build or
   the stack's equivalents). Ask only if the brief leaves the stack open and it
   matters. These fill `{{COMMANDS}}`, `{{CHECK_COMMANDS}}` in CLAUDE.md and
   both agents.
2. **Write the full spec first, then split it.** Architecture and file layout,
   interfaces, the feature catalogue, design rules, quality rules. Each topic
   becomes one `docs/<topic>.md`. If the user supplied a long spec, move it
   verbatim (by line range), do not paraphrase it.
3. **Write CLAUDE.md from the template**: one-paragraph project summary, the
   hard constraints table, commands, the docs index ("read X when doing Y"),
   then the template's fixed sections unchanged, then the project's "Do not"
   list. Keep it under ~8 KB; anything longer belongs in docs/.
4. **Write PLAN.md**: tasks small enough for one implementer run (one module,
   one controller, one section). Group into phases. Tag each with the docs
   section it needs. Task 1.1 is always the scaffold, with the safe-scaffold
   instructions from the template (never into a non-empty directory).
5. **Copy `scripts/progress.mjs`, create an empty `progress/`, and run
   `node scripts/progress.mjs`** to generate PROGRESS.md (Next: 1.1).
6. **Copy the two agents**, filling in the check commands.
7. Tell the user to start with
   `claude-local.sh <preset>` then "read PROGRESS.md and start the next task",
   and to keep Claude Code out of auto mode.

## Lessons built into the template (do not drop them)

- **Small CLAUDE.md.** It is re-sent every turn and loaded by every subagent;
  23 KB cost ~6K tokens per turn.
- **State in files, `/clear` instead of `/compact`.** Compaction loses detail;
  a fresh session reading PROGRESS.md does not.
- **A hard stop, not advice.** "Do one or two tasks per session" was read as a
  suggestion: KAT ran ~10 tasks in one session until Claude Code showed 14% left
  before auto-compact. The rule is now a hard stop after two tasks with a fixed
  final message telling the user to `/clear`.
- **Subagents with short replies.** File reads and tool output stay out of the
  main context. 15-line replies, never whole files or diffs.
- **One request at a time.** The router serves one slot (`parallel = 1`), so
  subagents queue; the template says to run them one by one.
- **Pick a model whose prompt state fits the RAM cache.** Switching between
  main chat and subagent evicts the slot; llama-server restores it from a RAM
  cache (`--cache-ram`, 8 GB). MoE models with small KV (KAT-Coder, Qwen3.6,
  Qwen3.8 Q6) restore in well under a second. Gemma 4 31B with f16 KV exceeded
  8 GB at ~45K and re-read the whole context on every switch (~75 s).
- **No auto mode.** Its safety classifier is another request to the same
  single-slot model; it timed out and denied actions in the Gemma session.
- **Non-interactive commands only, and never scaffold in place.**
  `npm create vite .` in a non-empty directory offers to delete files.
- **A runtime check before "done".** KAT finished all 25 tasks with typecheck,
  lint, 70 tests and the build green, and the page still threw on every load
  (a bad `requestIdleCallback` argument), left the hero and feature grid at
  opacity 0, requested frames by the wrong file names, and had a 1.08:1 Buy
  button. Nothing in the loop ever loaded the page. CLAUDE.md now has a final
  verification phase: `smoke.mjs` must exit 0, with each finding fixed through
  a note.
- **No images for text-only presets.** `claude-local.sh` blocks image Reads on
  non-vision presets; the template tells the model to check output by DOM or
  pixel scripts and leave visual checks to the human.
- **Trim command output** (`| tail -40`) and grep before reading.
- **No hand-edited status files.** KAT, editing PROGRESS.md by hand, appended
  six `## Log` headings and a stale second `## Next` (1.5 while on 3.4), and the
  main chat and subagent both edited PLAN.md. Rules did not stop it; taking the
  pen away did. `scripts/progress.mjs` is the only writer, Next is computed from
  PLAN.md, only the implementer records tasks, and `progress.mjs check` (run by
  test-runner) fails on any drift. `resolve` requires `--reason`: KAT closed a
  review note (a `setTimeout` the spec forbids) without changing the code or
  saying why; now the reason is kept in progress/resolved.md and shown in
  PROGRESS.md.
