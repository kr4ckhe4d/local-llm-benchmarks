# AGENTS.md: how to work in this repo

You are building **a realistic Japanese pagoda garden on a floating island**, rendered in the browser
with Three.js. Full brief and acceptance checks: `.ai/project.md`. Task list: `.ai/tasks.md`.
Where the last session left off: `.ai/handoff.md`.

You work autonomously in a loop. Nobody answers questions mid-run: make the call yourself, write the
decision in `.ai/decisions.md` with one line of reasoning, and keep going.

## Start of every session

1. Read `.ai/handoff.md`, then `.ai/project.md` (skim after the first time), then `.ai/tasks.md`.
2. `git log --oneline | head -15` and `git status` to confirm the state matches the handoff.
3. Pick the task: a `[~]` (partial) task first, otherwise the first `[ ]` task whose dependencies are `[x]`.
   Work on **one task per session**.
4. Run `node tools/shot.mjs --all` once before changing anything (if the scene exists yet) so you know
   the starting state.

## While working

- Make small steps and check each one in the browser: `node tools/shot.mjs --name <view> --query "<params>"`
  or `--all`. It prints JSON with console errors, FPS and `window.__diag`, and writes `shots/<name>.png`.
  **Open the PNGs with the read tool and look at them.** Judge them against the rubric in `.ai/project.md`
  ("Realism rubric"). Numbers alone do not tell you whether it looks real.
  If your model cannot read images (the read tool returns no picture), use the `image` stats in the
  JSON instead and be strict: `darkPct` > 25 or `brightPct` > 10 means bad exposure; `edgePct` < 6 means
  the frame is mostly flat colour (missing textures/detail); `colours4bit` < 300 means flat shading;
  `huesPct` should show the expected palette (sky blue + greens by day, pink from blossoms, orange at
  sunset, dark blue + warm accents at night). Note in the handoff that the review was stats-only.
- Zero console errors is a hard rule. Fix errors before moving on.
- Commit after each working step (`git add -A && git commit -m "T0x: ..."`). Never leave the tree broken
  at a commit if you can avoid it.
- Keep `index.html` as the entry point. Code lives in `src/` as ES modules, Three.js is vendored in
  `vendor/three/` (no CDN at runtime, no build step, no bundler).
- If a task turns out too big, split it in `.ai/tasks.md` (T05 -> T05a, T05b), finish the first part,
  and hand off.
- If you are stuck on something for more than ~3 attempts, write down what you tried in
  `.ai/handoff.md`, choose a simpler approach that still meets the rubric, and move on.
- Do not edit `.pi/extensions/goal-loop.ts` or `tools/shot.mjs` unless the task says so. If `shot.mjs`
  has a bug that blocks you, fix it minimally and note it in the handoff.

## Finishing a task (required, in this order)

1. Verify the task's **Done when** criteria with `node tools/shot.mjs --all`: zero errors, FPS target
   held, screenshots reviewed.
2. Tick it in `.ai/tasks.md`: `[x]` done, or `[~]` partial with a note of what is left.
3. Add any new tasks you discovered (with **Done when** lines) to `.ai/tasks.md`.
4. **Rewrite** `.ai/handoff.md` (not append) using its template: state of the scene, what this session
   did, measured numbers, known problems, exact next step. The next session has no memory of this one.
5. `git add -A && git commit`.
6. Call the `task_complete` tool (`task_id`, `status`, `summary`). Then end your turn with one line.
   A new session starts automatically and reads the handoff.

If the context-full warning arrives, do steps 2-6 with status `partial` right away.

## Finishing the project

When every task is `[x]` and every acceptance check in `.ai/project.md` passes **in this session**,
run the final review task, commit, then call `goal_complete` with the evidence. That stops the loop.
Do not call it early: a later session can always add polish tasks instead.

## Environment

- Linux, Node 26, `google-chrome-stable`, GPU: AMD RX 9070 XT (headless Chrome uses it via Vulkan, so
  FPS from `shot.mjs` is meaningful; headless rAF caps at about 60).
- Network is available for one-off downloads (npm, CC0 textures). Record every downloaded asset in
  `assets/CREDITS.md` (source URL + license). Only CC0 or similarly free licenses.
- Local preview for a human: `python3 -m http.server 8000` then open http://localhost:8000/.
