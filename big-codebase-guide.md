# Using these models on a big codebase

Rewritten 2026-10-06 for the current box: two cards (R9700 + RX 9070 XT,
48.9 GB, [r9700+rx9070.md](r9700+rx9070.md)), llama.cpp b11434, and Claude Code
working on every 128k preset ([claude-harness.md](claude-harness.md)). The
2026-08-09 version was written for one 16 GB card and Qwen3.6 with CPU offload.
Its numbers no longer apply, but its two central points survive below:
budget the context and protect the prompt cache.

**The one idea:** a codebase does not go *into* the context. The context is
working memory for one task. The project's memory lives on disk, in its code,
tests, notes and git history. A big codebase gets written by many short,
focused sessions that read and update that memory, not by one session that
holds everything.

## Size it up

Code tokenizes at roughly **10 tokens per line**.

| Context | ≈ Lines | ≈ Files (150 lines) | Left after Claude Code's ~20k prompt |
|---|---|---|---|
| 128K | ~13,000 | ~85 | ~110K, ~70 files |
| 256K | ~26,000 | ~170 | ~240K, ~160 files |

A big codebase is thousands of files, so neither tier holds it. The job is
choosing the few thousand lines a task needs, and arranging the code so that
number stays small.

## 1. Design the code for small context

This is the lever that matters most, and it is a design choice, not a tooling
one.

* **Modules with narrow interfaces.** Types, signatures and contracts in files
  that can be read without the implementation behind them.
* **The target:** any one task needs its own module plus the *interfaces* of
  its neighbours, usually 5-20K tokens however large the repo.
* A task that needs 200K tokens of context to understand is a design problem.
  A bigger window does not fix it.

## 2. Make the repo the memory

* **`ARCHITECTURE.md`** at the root, short: module map, data flow, invariants.
  Add one per module where the module has real complexity.
* **`CLAUDE.md`** (Claude Code) or **`CONVENTIONS.md`** (aider, template in this
  repo): the rules the model must follow, read every session.
* **Generate the docs once with map-reduce** (section 6), then keep them updated
  as part of each task, not as a separate chore.
* **For multi-step work, a `PLAN.md`** with numbered steps, written by the
  model. Each step then runs as a **fresh session** that reads the plan, does
  one step, runs the tests, ticks the step off and commits. The plan and git
  carry the state between sessions, not the conversation.

## 3. Let the model fetch, don't pre-load

* Use an agent harness with tools (search, read a file or a line range, list a
  directory, run tests) and let the model pull what it needs.
  [Claude Code via `claude-local.sh`](claude-harness.md) now works on all 13
  128k presets. [aider](aider-harness.md) is the alternative: its *repo map*
  (a ranked symbol index without bodies) is built for exactly this, and its
  system prompt is far smaller than Claude Code's ~20k.
* **Tests and the compiler are the ground truth.** A model that can run them
  does not need to hold the whole program in its head, and its mistakes
  surface in seconds instead of in review.
* For a quick scripted task without a harness, retrieve first, then prompt:
  `rg -l 'handleAuthToken' src/`, plus the matching files and a short repo map.

## 4. Treat 128K/256K as headroom, not a target

**Recall is not the problem.** It has been measured: Qwen3-Coder-Next found 5/5
facts at every depth up to 241K, including semantic near-miss distractors at
mid-context ([README § Context quality](README.md#context-quality-measured-not-assumed)).
The costs of a long context are time and cache, not lost information:

* **Cold prefill.** Qwen3.8 reads ~1,000 tok/s at 128K depth, so a cold 128K
  context is about **2 minutes** before the first token
  ([llama-b11434.md](llama-b11434.md)).
* **Warm turns are cheap.** With the prefix cached, a Claude Code turn costs
  **3-7 s** on most models, because only the new ~1-4K tokens are processed
  ([claude-harness.md § Speed](claude-harness.md#speed-the-prompt-cache-now-does-the-work)).
* **Anything that changes the prefix throws the cache away**: reordering files,
  editing the system prompt or `CLAUDE.md` mid-session, inserting a file ahead
  of others, compaction, switching model. Append, never insert.

So keep a session's working context to **roughly 50-75K** even on a 256K
preset (budget sketch at the end), and when it grows past that, finish the
step, update `PLAN.md` and start a fresh session.
Auto-compaction works, but each compaction is a new cold prefix.

Two models do not get the warm-turn benefit. Laguna and Muse showed no prompt
cache reuse across sessions in the Claude Code speed test (likely their
sliding-window attention, not yet tested). Laguna prefills fast enough not to
matter; Muse does not.

## 5. Use two models, by role

| Role | Preset | Why |
|---|---|---|
| **Writing code, default** | `gemma4-26B-A4B-vision-128k` | 143 tok/s, 3.8 s warm Claude Code turns, 37/50 on code-quality, reads screenshots |
| **Hard problems** | `qwen3.8-27B-128k` / `-256k`, or `-q8-128k` | Thinks before it answers (~17 s turns); Q8 is near-lossless |
| **Reading, summarising, search** | `gemma4-26B-A4B-32k` or `gpt-oss-20b-A3.6B-32k` | 143 / 147 tok/s for map-reduce and "where is X handled" |
| **Long single-pass reads** | `qwen3.6-35B-A3B-256k` or `gemma4-26B-A4B-256k` | Full 256K with no CPU offload; speed flat with context |

Only one model is resident at a time (`--models-max 1`), but swapping costs
one cold load, about 10-40 s with `load-mode = dio`. Matching the model to
each step is worth that.

## 6. Repo-wide questions: map-reduce

For questions no single task covers, such as an architecture review or "how
does auth flow through the system":

1. **Map:** summarise each file or module on its own, using the fast model at
   32K. These are small, cheap calls and can be scripted.
2. **Reduce:** feed the summaries, not the source, into one call on the strong
   model at 128K for the synthesis.

The expensive call then scales with the size of the summaries, not of the
repo. This is also how to produce the first `ARCHITECTURE.md` (section 2).

Beyond-native contexts (512K, 1M with YaRN) loaded on the single card in
August, but they are deliberately not presets: prefill collapses at that size,
and quality past the trained range is unmeasured. Map-reduce stays cheaper.

## 7. If I were doing it

Use a frontier model for the expensive moments: the initial architecture, the
plan, and hard cross-cutting bugs. Then let the local models do the volume,
one `PLAN.md` step at a time, in fresh sessions, with tests after every step.
The 26-35B local models are good at well-specified local edits. They are
weakest at the global reasoning that a limited window also makes hard, and
that is where a frontier model earns its cost.

## Budget sketch: a Claude Code session at 128K

| Item | Tokens |
|---|---|
| Claude Code system prompt + tool schemas | ~20,000 |
| `CLAUDE.md` + `ARCHITECTURE.md` + `PLAN.md` | ~3,000-6,000 |
| Files read for the task (module + neighbours' interfaces) | ~10,000-30,000 |
| Conversation, tool output, test runs | ~10,000-20,000 |
| **Comfortable working total** | **~45,000-75,000** |
| Headroom left in the 131,072 window | ~55,000-85,000 |

Past ~75K, the next step usually belongs in a new session.
