# AGENTS.md: how to work in this repo

You are building **{{GOAL_ONE_LINE}}**. Full brief and acceptance checks: `.ai/project.md`.
Task list: `.ai/tasks.md`. Where the last session left off: `.ai/handoff.md`.

You work autonomously in a loop, **one task per session**. Nobody answers questions mid-run: make the
call yourself, write the decision in `.ai/decisions.md` with one line of reasoning, and keep going.

## Start of every session

1. Read `.ai/handoff.md`, then `.ai/project.md` (skim after the first time), then `.ai/tasks.md`.
2. `git log --oneline | head -15` and `git status` to confirm the state matches the handoff.
3. Pick the task: a `[~]` (partial) task first, otherwise the first `[ ]` task whose dependencies are `[x]`.
   That is your only task this session.
4. Run the verification command once before changing anything (if there is anything to verify yet) so
   you know the starting state:
   `{{VERIFY_ALL}}`

## While working

- Make small steps and check each one: {{VERIFY_HOW}}
- {{HARD_RULES}}
- Commit after each working step (`git add -A && git commit -m "T0x: ..."`). Avoid broken commits.
- {{CODE_LAYOUT}}
- If a task turns out too big, split it in `.ai/tasks.md` (T05 -> T05a, T05b), finish the first part,
  and hand off.
- If you are stuck on something for more than ~3 attempts, write down what you tried in
  `.ai/handoff.md`, choose a simpler approach that still meets the brief, and move on.
- Do not edit `.pi/extensions/goal-loop.ts` or the files in `tools/` unless the task says so. If a tool
  has a bug that blocks you, fix it minimally and note it in the handoff.

## Finishing a task (required, in this order)

1. Verify the task's **Done when** criteria with `{{VERIFY_ALL}}`.
2. Tick it in `.ai/tasks.md`: `[x]` done, or `[~]` partial with a note of what is left. Tick only this
   one task.
3. Add any new tasks you discovered (with **Done when** lines) to `.ai/tasks.md`. Do not plan them in
   detail and do not start them.
4. **Rewrite** `.ai/handoff.md` (not append) using its headings. The next session has no memory of this
   one. Keep the "Gotchas" section: carry forward every gotcha that still applies.
5. `git add -A && git commit`.
6. Call the `task_complete` tool (`task_id`, `status`, `summary`). Then end your turn with one line.
   After that call every other tool is blocked; a new session starts automatically.

If the context-full warning arrives, do steps 2-6 with status `partial` right away.

## Finishing the project

When every task is `[x]` and every acceptance check in `.ai/project.md` passes **in this session**,
commit, then call `goal_complete` with the evidence. That stops the loop. Do not call it early: a later
session can always add polish tasks instead.

## Environment

{{ENVIRONMENT}}
