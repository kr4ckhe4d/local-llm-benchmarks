#!/usr/bin/env node
// Goal-loop commands for Claude Code: the counterpart of pi's task_complete / goal_complete tools.
//
//   node tools/loop.mjs task-complete <task_id> <done|partial> "<summary>"
//   node tools/loop.mjs goal-complete "<evidence>"
//   node tools/loop.mjs status
//
// task-complete is refused unless .ai/handoff.md was rewritten in this session, the git tree is clean, and at
// most one task was newly ticked [x] this session. Once accepted it writes .ai/loop/task-done: from then on the
// PreToolUse hook blocks every tool call, so the session has to end, and run-loop.sh starts a fresh one.
// goal-complete is refused while any task is [ ] or [~] or the tree is dirty; it writes .ai/GOAL_MET.
import { execSync } from "node:child_process";
import { existsSync, readFileSync, statSync, writeFileSync, appendFileSync, mkdirSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const p = (f) => join(ROOT, f);
const LOOP = p(".ai/loop");
const fail = (msg) => { console.error(`Refused: ${msg}`); process.exit(1); };

export function openTasks(root = ROOT) {
  try {
    return readFileSync(join(root, ".ai/tasks.md"), "utf8").split("\n").filter((l) => /^\s*- \[( |~)\]/.test(l));
  } catch { return null; }
}
export function doneIds(root = ROOT) {
  const ids = new Set();
  try {
    for (const l of readFileSync(join(root, ".ai/tasks.md"), "utf8").split("\n")) {
      const m = l.match(/^\s*- \[x\]\s*\**\s*([A-Za-z]*\d+[a-z]?)/i);
      if (m) ids.add(m[1]);
    }
  } catch { /* no tasks file */ }
  return ids;
}
export function session(root = ROOT) {
  try { return JSON.parse(readFileSync(join(root, ".ai/loop/session.json"), "utf8")); } catch { return null; }
}
const dirty = () => { try { return execSync("git status --porcelain", { cwd: ROOT, encoding: "utf8" }).trim(); } catch { return ""; } };

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const [cmd, ...args] = process.argv.slice(2);
  mkdirSync(LOOP, { recursive: true });
  const s = session();

  if (cmd === "task-complete") {
    const [id, status, ...rest] = args;
    const summary = rest.join(" ").trim();
    if (!id || !["done", "partial"].includes(status) || !summary)
      fail('usage: node tools/loop.mjs task-complete <task_id> <done|partial> "<summary>"');
    if (existsSync(p(".ai/loop/task-done"))) fail("task-complete is already recorded for this session. End your turn now.");
    if (!s) fail("no .ai/loop/session.json: run the project through ./run-loop.sh.");
    const h = p(".ai/handoff.md");
    if (!existsSync(h) || statSync(h).mtimeMs < s.start)
      fail(".ai/handoff.md was not rewritten in this session. Rewrite it for the next session, commit, then run this again.");
    const d = dirty();
    if (d) fail(`uncommitted changes. Commit them first (git add -A && git commit), then run this again.\n${d}`);
    const newly = [...doneIds()].filter((x) => !(s.done || []).includes(x));
    if (newly.length > 1)
      fail(`${newly.length} tasks were ticked [x] this session (${newly.join(", ")}). One task per session: set all but the one you worked on back to [ ] or [~], commit, and run this again.`);
    appendFileSync(p(".ai/loop/loop-log.tsv"), `${new Date().toISOString()}\t${id}\t${status}\t${summary.replace(/\s+/g, " ")}\n`);
    writeFileSync(p(".ai/loop/task-done"), `${id}\t${status}\n`);
    console.log("Recorded. End your turn now with a one-line summary. Every further tool call is blocked; run-loop.sh starts a fresh session that resumes from .ai/handoff.md.");
  } else if (cmd === "goal-complete") {
    const evidence = args.join(" ").trim();
    if (!evidence) fail('usage: node tools/loop.mjs goal-complete "<evidence>"');
    const open = openTasks();
    if (open === null) fail("no .ai/tasks.md");
    if (open.length) fail(`.ai/tasks.md still has ${open.length} open task(s) ([ ] or [~]).`);
    const d = dirty();
    if (d) fail(`uncommitted changes. Commit first.\n${d}`);
    writeFileSync(p(".ai/GOAL_MET"), `${new Date().toISOString()}\n${evidence}\n`);
    writeFileSync(p(".ai/loop/task-done"), "GOAL\tdone\n");
    console.log("Goal recorded as met. The loop has stopped. Give a short final report and end your turn.");
  } else if (cmd === "status") {
    const open = openTasks() || [];
    console.log(JSON.stringify({ session: s, open: open.length, next: open[0]?.trim() ?? null,
      taskDone: existsSync(p(".ai/loop/task-done")), goalMet: existsSync(p(".ai/GOAL_MET")) }, null, 1));
  } else {
    fail("usage: node tools/loop.mjs task-complete|goal-complete|status ...");
  }
}
