# Running Claude Code against the local router

Claude Code is the most demanding client anything on this box has served. It
sends a ~20k-token system prompt, dozens of tool schemas, and expects the
Anthropic Messages API rather than the OpenAI one. All of that works, but a few
separate things have to be right, and each one fails with an error that does
not name its cause.

> **Current state, re-verified 2026-10-06:** llama.cpp b11434 (`5e03bdd87`),
> two cards (R9700 + RX 9070 XT, [r9700+rx9070.md](r9700+rx9070.md)), Claude
> Code 2.1.290. **All 13 of the 128k presets drive Claude Code**, against 7 of
> 11 in August. The dense-Qwen template block is fixed with a patched chat
> template (below), gpt-oss-20b's grammar failure is gone on this build, and
> warm turns take **3-7 s on most models**, down from 22-62 s. The default is
> now **`gemma4-26B-A4B-vision-128k`**, which can also read screenshots.
>
> The original findings were verified 2026-08-23/24 against llama.cpp `b10463`
> (`7c35571e5`) on one 16 GB card, from Claude Code 2.1.231 (Linux) and 2.1.241
> (macOS, over the LAN). Sections still describing that state say so.

The client-side driver is `claude-local.sh`, which encodes all four fixes. This
file is why it does what it does.

---

## The part that needed no work

**llama.cpp serves the Anthropic Messages API natively.** No translation proxy,
no LiteLLM, no `claude-code-router`. This build routes:

```
tools/server/server.cpp:250   /v1/messages
tools/server/server.cpp:267   /v1/messages/count_tokens
```

All three behaviours Claude Code depends on were checked directly rather than
assumed:

| Requirement | Result |
|---|---|
| Anthropic response envelope | `type:message`, `content[]` blocks, `stop_reason`, `usage` ✓ |
| SSE streaming | `message_start`, `content_block_start`, `content_block_delta`/`text_delta` ✓ |
| Tool use | `tool_use` block with `id`/`name`/`input`, `stop_reason:"tool_use"` ✓ |
| Token counting | `POST /v1/messages/count_tokens` → `{"input_tokens":45}` ✓ |

This is the piece most likely to have blocked the whole idea, and it is the
piece that needed nothing.

---

## Gotcha 1: the system prompt does not fit in 32k

```
API Error: 400 request (41796 tokens) exceeds the available context size (32768 tokens)
```

**Claude Code's system prompt measured 41,796 tokens** before a single word of
conversation, with the claude.ai connectors attached. With MCP disabled — which
gotcha 2 makes mandatory — it is **24,000–27,000 tokens**, varying by tokenizer:
24,410 for Gemma 4, 25,996 for Laguna, 27,216 for Qwen3-Coder, and **48,378 for
Muse Glimmer**, whose tokenizer turns the identical text into nearly twice as
many tokens. Either way, every 32k preset is unusable — not slow, not degraded,
unable to answer one request.

128k is the smallest practical bucket. `claude-local.sh` refuses anything under
64k with a message that says so, rather than letting the router produce the
error above.

**2026-10-06:** on Claude Code 2.1.290 the prompt is smaller, **~20k tokens**
for most models (19,250 Qwen3.6 to 21,449 Qwen3.8, per the first request of the
compat task below). Muse is still the outlier, its tokenizer roughly doubling
it. A 32k preset would now accept the first request but leave ~10k for an
actual task, so the 64k floor stays.

Claude Code also assumes a 200k window for model names it does not recognise,
which will silently mis-drive auto-compaction. Set it explicitly:

```
CLAUDE_CODE_MAX_CONTEXT_TOKENS=131072
```

**Cost note (2026-08, one card).** Prefilling that prompt is 21.5s of Laguna's 21.9s first turn —
96% of the wait, before a single token appears. It is not paid again on the
next turn: llama.cpp caches the prefix, and a `--continue` follow-up lands in
**3.1s**. The full cost returns after compaction, a model switch, or starting a
new session. Numbers and method in `benchmarks/claude-harness-speed.txt`.

---

## Gotcha 2: three Notion schemas break tool calling entirely

```
API Error: 400 Failed to initialize samplers: failed to parse grammar
```

llama.cpp compiles every tool's JSON Schema into a GBNF grammar for constrained
decoding. If **one** schema fails to convert, the whole request is rejected and
**no tool calling works at all**.

Claude Code sent **128 tool schemas** here. Exactly three fail, all from the
claude.ai Notion connector:

| Tool | Size | Notable keywords |
|---|---|---|
| `notion-create-comment` | 8,233 B | `anyOf`, `allOf` |
| `notion-query-meeting-notes` | 16,256 B | `anyOf` |
| `notion-search` | 3,863 B | — |

The other **125 compile fine**, verified by replaying the captured payload with
those three removed. It is not a size limit and not a single bad keyword —
`anyOf`, `allOf`, `$schema`, `propertyNames`, `pattern`, `format:uri`,
`additionalProperties:false` and 9007199254740991-scale integer bounds all
compile individually when probed in isolation.

**`--allowedTools` does not help.** It gates *permission*, not *transmission* —
all 128 schemas go to the server regardless of what is allowed. The fix is to
stop the connectors loading at all:

```
--strict-mcp-config --mcp-config '{"mcpServers":{}}'
```

This is mandatory, not hygiene. Without it, Claude Code against this router has
no tools whatsoever.

> Diagnosis method, since the error names nothing: run a logging reverse proxy
> in front of the router, capture the request body, then bisect the `tools`
> array against `/v1/messages` one schema at a time.

**2026-10-06:** Claude Code 2.1.290 now refuses to load the claude.ai connectors
at all when `ANTHROPIC_AUTH_TOKEN` is set ("claude.ai connectors are disabled
because ANTHROPIC_API_KEY or another auth source is set"), so the Notion
schemas no longer reach the router through `claude-local.sh` either way. The
grammar failure itself was not re-tested. `--strict-mcp-config` stays, because
it also keeps any *local* MCP servers' schemas out.

---

## Gotcha 3: Claude Code has four model slots, not one

```
API Error: 400 model 'claude-sonnet-5' not found
```

Setting `ANTHROPIC_MODEL` covers the main slot. **Sonnet, Opus and Haiku each
have their own**, and unset ones fall back to real Anthropic model names that
the router has never heard of. Anything touching those slots — subagents,
session titling, background work — 400s.

Two fixes, and the server-side one cannot be forgotten:

**Server (preferred).** `--alias` is comma-separated, so one preset can answer
to every name. This is committed in `models-preset.ini`:

```ini
[gemma4-26B-A4B-vision-128k]
alias = gemma4-vision-128k,claude-sonnet-5,claude-opus-5,claude-haiku-4-5-20251001
```

Verified: a `/v1/messages` request for `claude-sonnet-5` returns
`"model":"gemma4-26B-A4B-vision-128k"`. (Until 2026-10-06 these aliases sat on
`laguna-33B-A3B-128k`, the old default. They follow `claude-local.sh`'s default.) Aliases do **not** appear as separate entries
in `/v1/models`, so the Open WebUI dropdown is unchanged.

**Client.** Pin all four explicitly:

```
ANTHROPIC_MODEL / ANTHROPIC_DEFAULT_SONNET_MODEL /
ANTHROPIC_DEFAULT_OPUS_MODEL / ANTHROPIC_DEFAULT_HAIKU_MODEL
```

**They must all name the same model.** The router runs `--models-max 1`, so
pointing the Haiku slot at something smaller — tempting, since it only does
background work — would evict the main model and force a full reload on every
background task.

`[claude-code:unrecognized_model]` still appears on startup. It is harmless:
the session-title generator noting a non-Anthropic name.

---

## Gotcha 4: one screenshot kills the session

```
500 image input is not supported
```

Every text-only preset fails like this. A single image in context produces the
above, and Claude Code then **retry-loops** on it (`attempt 5/10`), so one
screenshot ends the session.

**2026-10-06: the Gemma 4 vision presets do not have this problem.** With
`gemma4-26B-A4B-vision-128k`, Claude Code's `Read` on `vision-probe.png`
returned the rendered code `PROBE-770487`, all three shapes and colours, and
the arithmetic answer, in 2 turns and 12.9 s. The same request on
`gemma4-26B-A4B-128k` (no projector) still gets the 500 and the retry loop.
That is why the vision preset is now `claude-local.sh`'s default, and why
`--chrome` allows `take_screenshot` when the model name contains `vision`. Everything
below holds for the text-only presets.

Telling the model not to take screenshots does not work — it is an instruction,
not a constraint, and it cannot un-send a request already in flight. **Remove
the tool instead.**

Of `chrome-devtools-mcp`'s 29 tools, exactly one returns an image:
`take_screenshot`. `claude-local.sh --chrome` allowlists the other 20
text-returning tools and omits it, which makes the failure structurally
impossible.

**`take_snapshot` is the replacement.** It returns the page's accessibility
tree as text — which is the thing a text-only model can actually reason about.
With `evaluate_script` alongside it, that covers most of what screenshots are
normally used for.

Note that `Read` will also send an image if pointed at a PNG. Same failure.

---

## Chrome DevTools

Not configured by default on either machine — the Chrome tools in the Claude
desktop app are a separate integration. `chrome-devtools-mcp` is the CLI one:

```json
{"mcpServers":{"chrome-devtools":{"command":"npx",
  "args":["-y","chrome-devtools-mcp@latest","--isolated"]}}}
```

**All 29 schemas compile**, individually and together — no repeat of the Notion
problem. Verified end to end: navigate to a page, `evaluate_script` for
`document.title`, correct result returned, driven by Laguna over the LAN.

`--isolated` uses a throwaway profile rather than the real Chrome session, so
the model is not driving a browser logged into live accounts. Worth keeping.
Add `--headless` for no visible window.

`--strict-mcp-config --mcp-config <file>` does **both** jobs at once here: it
enables Chrome DevTools *and* excludes the Notion connectors. Dropping it to
get Notion back breaks tool calling entirely (gotcha 2).

---

## Over the LAN

The router already binds `0.0.0.0`, so nothing needs changing on the server.

| | |
|---|---|
| Router | `http://192.168.4.228:8090` |
| **Not** the router | `:8080` is **Open WebUI** — the easiest mistake to make |
| Subnet | interface is **`/22`**, so `192.168.4.0–192.168.7.255` is one subnet |
| Firewall | `ufw` active but not blocking 8090 — confirmed by curl **from** the laptop |

The `/22` matters: `192.168.5.24` and `192.168.4.228` look like different
networks under the usual `/24` assumption, but are in-subnet neighbours here.
No routing involved.

Testing reachability from the server is not a valid check — traffic to the
box's own LAN IP goes via loopback and can bypass `ufw` rules that would apply
to a real LAN peer. Test from the client.

**There is no authentication.** `ANTHROPIC_AUTH_TOKEN=local` is accepted
because llama.cpp is not checking anything; the endpoint is open to the whole
`/22`. Fine on a trusted network. `llama-server --api-key <key>` gates it.

---

## Verified working

All from the MacBook, over the LAN, against the router (2026-08; the file-edit
loop and image reading were re-verified locally on 2026-10-06, see below):

| Capability | Evidence |
|---|---|
| Chat | round trip through `/v1/messages` |
| File editing | read `calc.py`, found `a - b`, edited to `a + b`, reported accurately |
| `WebFetch` | fetched `example.com`, returned heading `Example Domain` |
| Chrome DevTools | navigated, `evaluate_script`, returned `document.title` |
| Model switching | `claude-local <preset>`, context derived from the preset name |

`WebFetch` runs entirely locally — its page-summarisation step uses the Haiku
slot, which is pinned to the same local model.

---

## Which models actually work: 13 of 13

`benchmarks/claude-compat.sh` runs one real agentic task per preset, not a chat
probe. The fixture is a two-file repo where `add()` returns `a - b` and a test
expects 5. The model must read it, fix the file with `Edit`, run the test with
`Bash`, and report. Pass means the file on disk is fixed and the test passes
afterwards. Output is in `benchmarks/claude-compat.txt` and the raw transcripts in
`benchmarks/raw/compat-*`.

| Preset | Pass | Turns | API s | August |
|---|---|---|---|---|
| `gpt-oss-20b-A3.6B-128k` | ✅ | 8 | **9.5** | ❌ grammar |
| `laguna-33B-A3B-128k` | ✅ | 5 | 11.8 | ✅ |
| `laguna-33B-A3B-q8-128k` | ✅ | 5 | 14.1 | ✅ |
| `qwen3.5-9B-uncensored-128k` | ✅ | 5 | 14.3 | ❌ template |
| `gemma4-26B-A4B-128k` | ✅ | 6 | 15.8 | ✅ |
| `qwen3.6-35B-A3B-128k` | ✅ | 7 | 16.1 | ✅ |
| `gemma4-26B-A4B-vision-128k` | ✅ | 7 | 16.4 | not tested |
| `gemma4-26B-A4B-q8-128k` | ✅ | 7 | 17.8 | not tested |
| `qwen3.8-27B-128k` | ✅ | 6 | 23.8 | ❌ template |
| `qwen3.8-27B-q8-128k` | ✅ | 6 | 29.8 | not tested |
| `qwen3.5-27B-uncensored-128k` | ✅ | 5 | 33.1 | not tested |
| `glm-4.7-flash-30B-A3B-128k` | ✅ | 5 | 35.0 | ✅ |
| `muse-glimmer-30B-128k` | ✅ | 6 | 114.9 | ✅ |

Muse is slow here because its tokenizer turns the same prompt into ~106k input
tokens across the task, five times the others. `qwen3-coder-80B-A3B` from the
August table is no longer on disk.

### The dense-Qwen fix: a patched chat template

Claude Code sends a `system`-role message *after* the user message:

```
messages[0]  role=user     blocks=['text','text']
messages[1]  role=system   blocks=['text']
```

Qwen3.8's and Qwen3.5's Jinja templates raise `System message must be at the
beginning` on that shape (Qwen3.8 line 110). In August this was recorded as
"nothing to fix client-side", which is true, but it is fixable **server-side**.
The template is just text, and llama-server takes a replacement:

```
templates/qwen38-late-system.jinja    (Qwen3.8, all quants)
templates/qwen35-late-system.jinja    (Qwen3.5-27B and 9B; their templates are identical)
```

Each is the model's own embedded template with one line changed. Where it
raised, it now renders the late message as an ordinary ChatML system turn,
`<|im_start|>system\n…<|im_end|>`. The first system message still renders at
the top exactly as before. Every Qwen3.8 and Qwen3.5 preset sets
`chat-template-file`, and so does `switch-model.sh`. Verified by the table
above. The model reads the late system turn and completes the task.

`gpt-oss-20b`'s August failure was different: it loaded, then rejected the
built-in tool schemas at grammar compilation. It passes on b11434 with no
change on this side, so the fix came from upstream.

> A probe that sends tools plus a plain user message is **not** sufficient to
> establish compatibility. In August it passed all three Qwen models that then
> failed in real use. That is why `claude-compat.sh` drives a real task.

## Speed: the prompt cache now does the work

`benchmarks/claude-speed.sh`, 2026-10-06, b11434 on two cards
(`benchmarks/claude-harness-speed.txt`, raw envelopes in `benchmarks/raw/`).
Two separate `claude -p` sessions per preset with a no-tool prompt. COLD
includes loading the model, and WARM is the second session with the model
resident. `IN_tok` is what was *not* served from cache.

| Model | Cold s | **Warm s** | IN_tok (uncached) | Aug cold / warm |
|---|---|---|---|---|
| `qwen3.6-35B-A3B-128k` | 10.4 | **3.2** | 1,060 | 145.6 / 22.8 |
| `gemma4-26B-A4B-128k` | 12.2 | **3.5** | 3,438 | 43.7 / 32.7 |
| `gemma4-26B-A4B-vision-128k` | 12.4 | **3.8** | 3,580 | — |
| `gemma4-26B-A4B-q8-128k` | 13.6 | **3.8** | 3,510 | — |
| `gpt-oss-20b-A3.6B-128k` | 10.0 | **4.5** | 350 | — |
| `qwen3.5-9B-uncensored-128k` | 12.8 | 6.0 | 3,855 | — |
| `laguna-33B-A3B-128k` | 10.8 | 6.2 | 21,906 | 101.7 / 21.9 |
| `laguna-33B-A3B-q8-128k` | 12.6 | 6.7 | 21,970 | 176.9 / 37.5 |
| `qwen3.5-27B-uncensored-128k` | 27.9 | 11.4 | 3,793 | — |
| `glm-4.7-flash-30B-A3B-128k` | 36.0 | 17.2 | 2,410 | 167.6 / 54.6 |
| `qwen3.8-27B-128k` | 21.9 | 17.2 | 3,977 | — |
| `qwen3.8-27B-q8-128k` | 38.5 | 22.0 | 4,039 | — |
| `muse-glimmer-30B-128k` | 43.0 | 22.6 | 20,504 | 118.0 / 61.7 |

* **Cross-session prompt caching works now.** In August each `claude -p` session
  re-prefilled its whole ~26k prompt, because Claude Code varies cwd, date and
  session id inside it. Now most models report ~17k tokens as
  `cache_read_input_tokens` and re-process only the ~1-4k that changed. The warm
  turn is mostly the answer itself.
* **Laguna and Muse get no cache reads** (`IN_tok` ≈ the whole prompt). Both use
  sliding-window attention, which is the likely cause, but this was not tested
  (`--swa-full` would be the test). Laguna is still quick because it prefills
  ~3,500 tok/s; Muse is not.
* **Qwen3.8's 17 s is thinking, not prefill.** It emits ~770 output tokens
  against Qwen3.6's 179, inside the 1,024 reasoning budget. That is a choice
  per task, not a cost of the harness.
* The two cards are the other half of the change. Every MoE preset dropped CPU
  offload ([r9700+rx9070.md](r9700+rx9070.md)), so cold loads and prefill are
  several times faster.

## Choosing a model

Claude Code is an agentic loop. It rewards reliable tool calls and
instruction-following more than raw speed, and since every preset now passes,
the choice is about quality per second.

| | code-quality | Warm turn | Use it for |
|---|---|---|---|
| **`gemma4-26B-A4B-vision-128k`** (default) | **37/50** | **3.8 s** | Everyday work. Fast, top-tier on the code probe, and can read screenshots |
| `qwen3.8-27B-128k` | 30-39/50 by quant | 17.2 s | Harder problems where thinking pays. Best fidelity at Q8 |
| `qwen3.6-35B-A3B-128k` | not measured | **3.2 s** | Fastest warm turn; a reasonable alternative default |
| `gpt-oss-20b-A3.6B-128k` | not measured | 4.5 s | Quick, small tasks |
| `laguna-33B-A3B-q8-128k` | 27/50 | 6.7 s | Not recommended: lowest code score, no cache reuse |

* `code-quality` resolves about 4 checks in 50, and Qwen3.8 alone spans 30-39
  across quants. Read the column as "Gemma 4 and Qwen3.8 are in the same band,
  Laguna is below it", not as a strict order.
* **Gemma 4 vision replaces Laguna Q8 as the default.** In August the choice
  was between a fast weak model (Laguna, 3.1 s follow-ups, 27/50) and a slow
  strong one. Gemma now has both the speed and the score. The vision projector
  costs nothing in speed (3.8 s against the text preset's 3.5) and removes
  gotcha 4.
* Switch per task with `claude-local <preset>`. Swapping models costs one cold
  load, about 10-40 s.

## `claude-local.sh`

```bash
claude-local list                        # what the router is serving
claude-local                             # default model, interactive
claude-local qwen3.8-27B-128k            # switch model
claude-local --chrome                    # add Chrome DevTools (screenshots only on vision presets)
claude-local -p "fix the bug"            # anything else passes through
```

`ROUTER` and `CLAUDE_LOCAL_MODEL` override the defaults.

Written for **bash 3.2**, which is what macOS ships: no associative arrays, no
`${x,,}`, and empty arrays expanded as `${a[@]+"${a[@]}"}` to survive `set -u`.

One bug worth recording because its symptom is so misleading: pass-through args
were originally accumulated in an unquoted string, so `-p "Reply with exactly:
SCRIPT-OK"` word-split and delivered only `Reply` to the model. The model then
replied *"I notice you've sent a simple 'Reply' message"* — which reads exactly
like the model ignoring instructions rather than a quoting bug in the harness.
Pass-through args are kept in an array now.
