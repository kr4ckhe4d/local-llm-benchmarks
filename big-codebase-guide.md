# Using these models on a real codebase

The [benchmarks](README.md) show Qwen3.6-35B-A3B at 32K context doing ~44 tok/s
generation and ~1,975 tok/s prompt processing on the ROCm build, with a
comfortable VRAM margin. This guide is about what to actually *do* with
that — because 32K (or even 128K) tokens is nowhere near "paste in the repo,"
and the naive approach (dump everything you can fit) is usually the wrong one
even when it technically fits.

## Size it up first

Code tokenizes at roughly **8-12 tokens/line** (denser than English prose).
Rule of thumb: **~10 tokens/line**.

| Context | ≈ Lines of code | ≈ Files (150-line avg) | Good for |
|---|---|---|---|
| 32K | ~3,200 | ~20 files | One task, a handful of related files |
| 128K | ~12,800 | ~85 files | A module/subsystem, a real refactor |

A "big codebase" is usually thousands of files. Neither tier holds that — so
the job is picking the *right* few thousand lines, not maximizing how many you
can cram in.

## Budget the context, don't just fill it

Whatever you stuff into the prompt has to share space with the system prompt,
tool definitions, conversation history, and — critically — **room left over
for the model's own output**. If you fill the context window with input, the
model has nowhere to write its answer and generation degrades or gets cut off
mid-response (`finish_reason: "length"`, as seen in earlier tests).

Worked example for Qwen3.6-35B-A3B at 32K (`-ncmoe 16 -ub 1024`):

| Budget item | Tokens |
|---|---|
| System prompt + tool schemas | ~1,500 |
| Repo map (file tree + signatures, no bodies) | ~500 |
| Retrieved/relevant code | ~18,000 |
| Conversation history | ~6,000 |
| **Reserved for model output** (`max_tokens`) | ~4,000 |
| **Total** | **~30,000 / 32,768** |

Leave slack the same way the VRAM tuning did — don't run a context budget at
100%, for the same reason `-ncmoe` wasn't tuned to the exact last free MiB:
real prompts vary in length and you don't want to discover the ceiling mid-task.

## Two strategies, pick based on task shape

### 1. Retrieval — for well-scoped tasks ("fix this bug," "add this endpoint")

Don't feed the model files "just in case." Find the relevant ones first, then
feed only those:

```bash
# find candidate files/symbols before touching the model at all
rg -l 'handleAuthToken' src/
rg -n 'class UserSession' src/
```

Assemble the prompt from: the task description, a short repo map for
orientation, and the *contents* of only the files that matched. This is cheap,
deterministic, and keeps token usage proportional to the task, not the repo.

For fuzzier queries where grep won't find the right files (e.g. "where do we
handle rate limiting," no literal string match), a lightweight embeddings
index over file/function summaries works better than either grepping harder
or feeding more files hoping something sticks.

### 2. Agentic / tool-use loop — for open-ended or multi-file tasks

Instead of pre-loading context, give the model tools (`read_file(path)`,
`grep(pattern)`, `list_dir(path)`) and let it pull in what it decides it needs,
turn by turn — the same pattern Claude Code itself uses. This scales far better
than retrieval-then-stuff for tasks where you don't know up front which files
matter.

**Caveat before building this on Qwen3.6 or Coder-Next:** earlier testing found
Qwen2.5-Coder-14B's tool-calling was broken — it reasoned about tool calls
correctly but emitted them as `<tools>...</tools>` plain text instead of the
structured `tool_calls` API field, a chat-template mismatch. (That model has
since been deleted; the detail is recorded here because the failure mode
recurs across models and is easy to misdiagnose as the model being bad at
tool use.)

**Verify whichever model you pick actually returns proper `tool_calls` with
`finish_reason: "tool_calls"` via `/v1/chat/completions` before relying on this
pattern** — if it has the same template issue, the retrieval strategy above is
the fallback. Serving with `--jinja` makes `llama-server` use the model's own
chat template and is the usual fix for Qwen tool-calling.

## Exploit prompt caching for repeated context

`llama-server`'s startup log shows a built-in prompt cache (`prompt cache is
enabled, size limit: 8192 MiB` — visible in `/tmp/llama-server.log`). Keep a
**stable prefix** — system prompt, repo map, core files referenced every turn —
identical across requests, and only the *new* part of each prompt (the actual
question, newly-retrieved files) pays full prompt-processing cost. Given prompt
tok/s is far higher than generation tok/s (1,975 vs 43.9 for Qwen3.6 @ 32K on
ROCm — a 45x ratio, up from 2.8x on the old Vulkan build), this matters most
for interactive back-and-forth, less for one-shot calls. The ROCm switch made
re-sending a large stable prefix dramatically cheaper relative to generation.

## Match context tier to the task

| Task | Context | Why |
|---|---|---|
| Single-file edit, quick question | 32K (`-ncmoe 16`, Qwen3.6) | Fastest (43.9 tok/s), plenty of room for one task |
| Multi-file refactor, "explain this subsystem" | 128K (`-ncmoe 20`, Qwen3.6) | Needs cross-file context; only ~5% slower generation |
| Serious coding over a large context | 128K-256K (Qwen3-Coder-Next) | Coding specialist; ~25 tok/s but answers without a reasoning preamble |
| "Summarize/understand the whole repo" | Neither — see map-reduce below | No single context tier holds a real codebase |

## When even 128K isn't enough: map-reduce

For genuinely repo-wide tasks (architecture review, "how does auth flow through
this whole system"), don't chase a bigger context window — it costs
disproportionate VRAM/RAM/speed for diminishing returns (see the README's
context-scaling table: gains shrink and cost grows well before 128K). Instead:

1. **Map:** summarize each file or module independently (small, cheap,
   parallelizable calls — this is where the fast 20B or 32K Qwen3.6 config earns
   its keep).
2. **Reduce:** feed those summaries (not the raw source) into one larger-context
   call for the actual synthesis/reasoning.

This keeps the expensive large-context call proportional to *summary* size, not
raw repo size, and is generally cheaper than reaching for a bigger context window.

That said, extreme context is more viable than it first looks — because both
Qwen models here use **hybrid attention**, where only 1 layer in 4 keeps a KV
cache (see [README § Why 1M context is possible](README.md#why-1m-context-is-possible-at-all-hybrid-attention)).
That is what makes 1M fit in 16GB at all; a conventional full-attention coder
would need ~52GB of KV at the same context.

Both models are verified working at 1,048,576 tokens on this card. **But 1M is
past their native 262,144, so it is deliberately not a `switch-model.sh`
preset** — it requires YaRN RoPE scaling, which trades away some short-context
quality. See [README § If you do want 1M](README.md#if-you-do-want-1m) for the
hand-rolled command; Qwen3-Coder-Next is the right pick there.

Two reasons the default stops at 256K:

1. **Prompt processing collapses.** Fitting 1M forces `-ub 256`, cutting
   Coder-Next from ~722 to ~236 tok/s. Generation barely moves (23.8 vs 25.8).
   Feeding the huge prompt is the slow part, not the reply — so 1M is worst
   exactly where you'd want it.
2. **You are outside the trained range.** Retrieval accuracy past the native
   window is an empirical question, not a given. If you rely on it, test it
   with a needle-in-a-haystack probe at your actual depth first.

Map-reduce stays the better choice for routine large-context work: it keeps the
model at its faster, natively-supported 128K/256K configs with `-ub 1024`.
