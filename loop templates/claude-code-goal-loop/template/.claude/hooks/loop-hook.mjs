#!/usr/bin/env node
// Claude Code hooks for the goal loop. One script handles four events (see .claude/settings.json).
// It acts only when LOOP_ACTIVE=1, which run-loop.sh sets, so opening the project interactively is unaffected.
//
//   SessionStart  adds the loop state (session number, open tasks, next task) and the loop rules to the context.
//   PreToolUse    after `tools/loop.mjs task-complete` succeeded, denies every tool call: the session has to end
//                 (in the pi run the model kept working after its handoff and drifted into the next task).
//   PostToolUse   at LOOP_CONTEXT_WARN_PCT (70) of LOOP_CONTEXT_WINDOW tokens, tells the agent to hand off a
//                 partial task; every LOOP_REMIND_EVERY (20) tool calls, repeats the loop rules.
//   Stop          if the agent tries to stop without task-complete, blocks the stop with a nudge (3 times at most
//                 per session); run-loop.sh counts a session that still ends that way as failed.
import { existsSync, readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const RULES = [
  "Work on exactly ONE task from .ai/tasks.md this session; do not start, plan in detail, or pre-build the next one.",
  "Finish a task in this order: verify its Done-when, tick it in .ai/tasks.md, rewrite .ai/handoff.md, git commit, run `node tools/loop.mjs task-complete <id> <done|partial> \"<summary>\"`, then end your turn with one line.",
  "Never ask the user questions; decide, log it in .ai/decisions.md, continue.",
  "Never edit .claude/, run-loop.sh or tools/loop.mjs unless the task says so.",
];
const NUDGE = "The goal loop is still running and you have not run `node tools/loop.mjs task-complete` (or goal-complete). " +
  "Do not wait for the user: keep working on the current task per CLAUDE.md. If you are blocked, record the blocker in " +
  ".ai/handoff.md, pick a workaround, and continue.";
const CONTEXT_WARN = "Context is getting full. Finish the smallest coherent step, commit, write a complete .ai/handoff.md " +
  "(what is done, what is half-done, exact next step), mark the task [~] in .ai/tasks.md if unfinished, then run " +
  "`node tools/loop.mjs task-complete <id> partial \"<summary>\"` and end your turn.";
const DENY = "The task is already recorded as complete for this session. Do not plan or start the next task: end your " +
  "turn now with a one-line summary. run-loop.sh starts a fresh session that reads .ai/handoff.md.";

const WINDOW = Number(process.env.LOOP_CONTEXT_WINDOW || 200000);
const WARN_PCT = Number(process.env.LOOP_CONTEXT_WARN_PCT || 70);
const REMIND_EVERY = Number(process.env.LOOP_REMIND_EVERY || 20);
const NUDGE_LIMIT = 3;

const input = JSON.parse(readFileSync(0, "utf8") || "{}");
if (process.env.LOOP_ACTIVE !== "1") process.exit(0);
const root = process.env.CLAUDE_PROJECT_DIR || input.cwd || process.cwd();
const f = (x) => join(root, x);
mkdirSync(f(".ai/loop"), { recursive: true });

// per-session counters live in .ai/loop/state-<session_id>.json
const stateFile = f(`.ai/loop/state-${input.session_id || "unknown"}.json`);
const state = (() => { try { return JSON.parse(readFileSync(stateFile, "utf8")); } catch { return { calls: 0, nudges: 0, warned: false }; } })();
const save = () => writeFileSync(stateFile, JSON.stringify(state));
const out = (o) => { process.stdout.write(JSON.stringify(o)); process.exit(0); };
const taskDone = existsSync(f(".ai/loop/task-done"));

function contextTokens() {
  // last assistant message's usage in the transcript: input + cache creation + cache read = context in use
  try {
    const lines = readFileSync(input.transcript_path, "utf8").trimEnd().split("\n");
    for (let i = lines.length - 1; i >= 0 && i > lines.length - 400; i--) {
      const r = JSON.parse(lines[i]);
      const u = r.type === "assistant" && r.message?.usage;
      if (u) return (u.input_tokens || 0) + (u.cache_creation_input_tokens || 0) + (u.cache_read_input_tokens || 0);
    }
  } catch { /* no transcript yet */ }
  return null;
}

switch (input.hook_event_name) {
  case "SessionStart": {
    let open = [];
    try { open = readFileSync(f(".ai/tasks.md"), "utf8").split("\n").filter((l) => /^\s*- \[( |~)\]/.test(l)); } catch { /* none */ }
    let n = "?";
    try { n = JSON.parse(readFileSync(f(".ai/loop/session.json"), "utf8")).n; } catch { /* not started by run-loop.sh */ }
    process.stdout.write(`Goal loop session ${n}. Open tasks: ${open.length}. Next: ${open[0]?.trim().slice(0, 160) ?? "none"}\n` +
      "Loop rules:\n- " + RULES.join("\n- ") + "\n");
    process.exit(0);
  }
  case "PreToolUse": {
    if (taskDone) out({ hookSpecificOutput: { hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: DENY } });
    process.exit(0);
  }
  case "PostToolUse": {
    if (taskDone) process.exit(0);
    state.calls++;
    const msgs = [];
    const t = contextTokens();
    if (!state.warned && t != null && t >= WINDOW * WARN_PCT / 100) { state.warned = true; msgs.push(CONTEXT_WARN); }
    if (state.calls % REMIND_EVERY === 0) msgs.push("Reminder of the loop rules (CLAUDE.md):\n- " + RULES.join("\n- "));
    save();
    if (msgs.length) out({ hookSpecificOutput: { hookEventName: "PostToolUse", additionalContext: msgs.join("\n\n") } });
    process.exit(0);
  }
  case "Stop": {
    if (taskDone || existsSync(f(".ai/GOAL_MET")) || existsSync(f(".ai/STOP"))) process.exit(0);
    if (state.nudges >= NUDGE_LIMIT) process.exit(0);
    state.nudges++;
    save();
    out({ decision: "block", reason: NUDGE });
  }
  default:
    process.exit(0);
}
