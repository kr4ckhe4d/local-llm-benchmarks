/**
 * goal-loop: keep pi iterating on .ai/tasks.md until the goal is met, one task per session.
 *
 * Flow
 *   1. The agent works on one task from .ai/tasks.md.
 *   2. When the task is done it updates .ai/tasks.md + .ai/handoff.md, commits, and calls `task_complete`.
 *   3. When the run settles, this extension starts a NEW session and sends the kickoff prompt,
 *      which tells the fresh agent to read AGENTS.md and .ai/handoff.md and carry on.
 *   4. When every task is done and the acceptance checks pass, the agent calls `goal_complete`,
 *      which writes .ai/GOAL_MET and stops the loop.
 *
 * Safety valves
 *   - Esc (aborted run) pauses the loop; `/loop-resume` continues, `/loop-next` forces a new session.
 *   - `touch .ai/STOP` stops all automatic continuation (delete the file to allow it again).
 *   - If a run ends without `task_complete`, the agent is nudged to continue (max NUDGE_LIMIT in a row).
 *   - At CONTEXT_WARN_PCT context usage the agent is told to checkpoint and hand off.
 *   - PI_LOOP_MAX_SESSIONS (default 60) caps how many sessions the loop will start.
 *
 * Drift guards (long sessions forget AGENTS.md)
 *   - LOOP_RULES are added to the system prompt of every run.
 *   - Every REMIND_EVERY turns the rules are re-sent as a steer message (they sit near the end of context).
 *   - After task_complete, every further tool call is blocked: the agent must end its turn instead of
 *     planning or starting the next task.
 *   - task_complete is refused if more than one task was newly ticked [x] in this session.
 */
import { execSync } from "node:child_process";
import { existsSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { Type } from "typebox";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

export const KICKOFF =
	"Continue the project loop. Read AGENTS.md, then .ai/handoff.md, then the files it points to. " +
	"Pick the next task as AGENTS.md describes and work until it meets its done-criteria. Do not stop to ask me questions.";

const NUDGE =
	"The loop is still running and you have not called task_complete or goal_complete. " +
	"Do not wait for me: keep working on the current task per AGENTS.md. If you are blocked, record the blocker in " +
	".ai/handoff.md, pick a workaround or the next unblocked task, and continue.";

const CONTEXT_WARN =
	"Context is getting full. Finish the smallest coherent step, commit, write a complete .ai/handoff.md " +
	"(what is done, what is half-done, exact next step), mark the task [~] in .ai/tasks.md if unfinished, " +
	"then call task_complete with status \"partial\". The next session will pick it up.";

const LOOP_RULES = [
	"LOOP RULE: work on exactly ONE task from .ai/tasks.md this session; do not start, plan in detail, or pre-build the next task.",
	"LOOP RULE: finish a task in this order: verify its Done-when, tick it in .ai/tasks.md, rewrite .ai/handoff.md, git commit, call task_complete, then end your turn with one line.",
	"LOOP RULE: never ask the user questions; decide, log it in .ai/decisions.md, continue.",
	"LOOP RULE: never edit .pi/extensions/goal-loop.ts or the verification tools unless the task says so.",
];
const REMIND =
	"Reminder of the loop rules (AGENTS.md):\n- " + LOOP_RULES.map((r) => r.replace("LOOP RULE: ", "")).join("\n- ");
const REMIND_EVERY = 20;

const NUDGE_LIMIT = 3;
const CONTEXT_WARN_PCT = 70;
const MAX_SESSIONS = Number(process.env.PI_LOOP_MAX_SESSIONS ?? 60);

export default function (pi: ExtensionAPI) {
	let rollover = false; // task_complete called in this session
	let goalMet = false;
	let paused = false;
	let nudges = 0;
	let contextWarned = false;
	let sessionStart = Date.now();
	let turns = 0;
	let doneAtStart = new Set<string>();

	const f = (ctx: ExtensionContext, p: string) => join(ctx.cwd, p);
	// Only drive the loop in the interactive TUI: print/json/rpc runs must exit normally.
	const active = (ctx: ExtensionContext) => ctx.mode === "tui" && existsSync(f(ctx, ".ai/handoff.md"));
	const stopped = (ctx: ExtensionContext) => existsSync(f(ctx, ".ai/STOP"));
	const status = (ctx: ExtensionContext, text: string | undefined) => {
		try { ctx.ui.setStatus("goal-loop", text); } catch { /* no UI */ }
	};
	const openTasks = (ctx: ExtensionContext) => {
		try {
			return readFileSync(f(ctx, ".ai/tasks.md"), "utf8")
				.split("\n")
				.filter((l) => /^\s*- \[( |~)\]/.test(l)).length;
		} catch { return -1; }
	};
	const doneIds = (ctx: ExtensionContext) => {
		const ids = new Set<string>();
		try {
			for (const l of readFileSync(f(ctx, ".ai/tasks.md"), "utf8").split("\n")) {
				const m = l.match(/^\s*- \[x\]\s*\**\s*([A-Za-z]*\d+[a-z]?)/i);
				if (m) ids.add(m[1]);
			}
		} catch { /* no tasks file */ }
		return ids;
	};
	const dirtyFiles = (ctx: ExtensionContext) => {
		try {
			return execSync("git status --porcelain", { cwd: ctx.cwd, encoding: "utf8" }).trim();
		} catch { return ""; }
	};
	// Count from the log so the cap survives extension reloads between sessions.
	const sessionsStarted = (ctx: ExtensionContext) => {
		try { return readFileSync(f(ctx, ".ai/loop-log.tsv"), "utf8").split("\n").filter(Boolean).length; } catch { return 0; }
	};
	const refreshStatus = (ctx: ExtensionContext) => {
		if (!active(ctx)) return;
		const open = openTasks(ctx);
		status(ctx, goalMet ? "loop: goal met" : stopped(ctx) ? "loop: STOP file" : paused ? "loop: paused (/loop-resume)" :
			`loop: ${open} open task(s), session ${sessionsStarted(ctx) + 1}`);
	};

	pi.on("session_start", async (_e, ctx) => {
		rollover = false;
		nudges = 0;
		contextWarned = false;
		turns = 0;
		sessionStart = Date.now();
		doneAtStart = doneIds(ctx);
		goalMet = existsSync(f(ctx, ".ai/GOAL_MET"));
		refreshStatus(ctx);
	});

	pi.registerTool({
		name: "task_complete",
		label: "Task complete",
		description:
			"Call this when the current task from .ai/tasks.md is finished (or when told to checkpoint because context is full). " +
			"Before calling: tick the task in .ai/tasks.md ([x] done, [~] partial), rewrite .ai/handoff.md for the next session, " +
			"and git commit everything. After this call, end your turn: a fresh session will start automatically and continue from .ai/handoff.md.",
		parameters: Type.Object({
			task_id: Type.String({ description: "Task id from .ai/tasks.md, e.g. T03" }),
			status: Type.Union([Type.Literal("done"), Type.Literal("partial")], { description: "done or partial" }),
			summary: Type.String({ description: "One or two sentences: what changed and how it was verified" }),
		}),
		async execute(_id, params, _signal, _onUpdate, ctx) {
			const handoff = f(ctx, ".ai/handoff.md");
			if (!existsSync(handoff) || statSync(handoff).mtimeMs < sessionStart) {
				throw new Error("Refused: .ai/handoff.md was not updated in this session. Rewrite it for the next session, commit, then call task_complete again.");
			}
			const dirty = dirtyFiles(ctx);
			if (dirty) {
				throw new Error(`Refused: uncommitted changes. Commit them first (git add -A && git commit), then call task_complete again.\n${dirty}`);
			}
			const newlyDone = [...doneIds(ctx)].filter((id) => !doneAtStart.has(id));
			if (newlyDone.length > 1) {
				throw new Error(`Refused: ${newlyDone.length} tasks were ticked [x] this session (${newlyDone.join(", ")}). ` +
					"One task per session: set all but the one you worked on back to [ ] or [~], commit, and call task_complete again.");
			}
			rollover = true;
			try {
				const line = `${new Date().toISOString()}\t${params.task_id}\t${params.status}\t${params.summary.replace(/\s+/g, " ")}\n`;
				writeFileSync(f(ctx, ".ai/loop-log.tsv"), line, { flag: "a" });
			} catch { /* best effort */ }
			return {
				content: [{ type: "text", text: "Recorded. End your turn now with a one-line summary; a new session will start and resume from .ai/handoff.md." }],
				details: params,
			};
		},
	});

	pi.registerTool({
		name: "goal_complete",
		label: "Goal complete",
		description:
			"Call ONLY when every task in .ai/tasks.md is [x] and every acceptance check in .ai/project.md passes, verified this session " +
			"with tools/shot.mjs --all (zero errors) and by looking at the screenshots. Stops the loop.",
		parameters: Type.Object({
			evidence: Type.String({ description: "How each acceptance check was verified, with numbers (fps, errors, screenshots reviewed)" }),
		}),
		async execute(_id, params, _signal, _onUpdate, ctx) {
			const open = openTasks(ctx);
			if (open !== 0) throw new Error(`Refused: .ai/tasks.md still has ${open} open task(s) ([ ] or [~]).`);
			const dirty = dirtyFiles(ctx);
			if (dirty) throw new Error(`Refused: uncommitted changes. Commit first.\n${dirty}`);
			writeFileSync(f(ctx, ".ai/GOAL_MET"), `${new Date().toISOString()}\n${params.evidence}\n`);
			goalMet = true;
			rollover = false;
			refreshStatus(ctx);
			return { content: [{ type: "text", text: "Goal recorded as met. The loop has stopped. Give the user a short final report." }], details: params };
		},
	});

	pi.on("before_agent_start", async (e, ctx) => {
		if (!active(ctx) || goalMet) return;
		for (const r of LOOP_RULES) if (!e.systemPromptOptions.promptGuidelines.includes(r)) e.systemPromptOptions.promptGuidelines.push(r);
	});

	// After task_complete the session is over: block further work so the agent cannot drift into the next task.
	pi.on("tool_call", async (e, ctx) => {
		if (!active(ctx) || !rollover) return;
		if (e.toolName === "task_complete") return;
		return {
			block: true,
			terminate: true,
			reason: "task_complete is already recorded. Do not plan or start the next task: end your turn now with a one-line summary. " +
				"A fresh session starts automatically and reads .ai/handoff.md.",
		};
	});

	pi.on("turn_end", async (_e, ctx) => {
		if (!active(ctx) || rollover || goalMet) return;
		turns++;
		if (turns % REMIND_EVERY === 0) pi.sendUserMessage(REMIND, { deliverAs: "steer" });
		if (contextWarned) return;
		const pct = ctx.getContextUsage()?.percent;
		if (pct != null && pct >= CONTEXT_WARN_PCT) {
			contextWarned = true;
			pi.sendUserMessage(CONTEXT_WARN, { deliverAs: "steer" });
		}
	});

	pi.on("agent_settled", async (e, ctx) => {
		if (!active(ctx)) return;
		refreshStatus(ctx);
		if (e.aborted) {
			paused = true;
			refreshStatus(ctx);
			return;
		}
		if (goalMet || paused || stopped(ctx)) return;
		if (rollover) {
			if (sessionsStarted(ctx) >= MAX_SESSIONS) {
				ctx.ui.notify(`goal-loop: reached PI_LOOP_MAX_SESSIONS=${MAX_SESSIONS}; not starting another session.`, "warning");
				return;
			}
			pi.sendUserMessage("/loop-next", { expandPromptTemplates: true });
			return;
		}
		if (nudges < NUDGE_LIMIT) {
			nudges++;
			pi.sendUserMessage(NUDGE);
		} else {
			ctx.ui.notify("goal-loop: agent stopped without task_complete after 3 nudges. Check it, then /loop-resume or /loop-next.", "warning");
		}
	});

	pi.registerCommand("loop-next", {
		description: "Start a fresh session that resumes from .ai/handoff.md",
		handler: async (_args, ctx) => {
			await ctx.waitForIdle();
			paused = false;
			const parent = ctx.sessionManager.getSessionFile();
			const res = await ctx.newSession({
				parentSession: parent,
				withSession: async (next) => {
					await next.sendUserMessage(KICKOFF);
				},
			});
			if (res.cancelled) ctx.ui.notify("goal-loop: new session cancelled", "warning");
		},
	});

	pi.registerCommand("loop-resume", {
		description: "Un-pause the loop and continue in this session",
		handler: async (_args, ctx) => {
			paused = false;
			nudges = 0;
			refreshStatus(ctx);
			pi.sendUserMessage(KICKOFF);
		},
	});

	pi.registerCommand("loop-pause", {
		description: "Stop automatic continuation until /loop-resume",
		handler: async (_args, ctx) => {
			paused = true;
			refreshStatus(ctx);
		},
	});
}
