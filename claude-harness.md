# Running Claude Code against the local router

Claude Code is the most demanding client anything on this box has served. It
sends a ~42k-token system prompt, 128 tool schemas, and expects the Anthropic
Messages API rather than the OpenAI one. All of that works — but four separate
things have to be right, and each one fails with an error that does not name
its cause.

Everything here was verified on 2026-08-23 against llama.cpp `b10463`
(`7c35571e5`), from Claude Code 2.1.231 (Linux, local) and 2.1.241 (macOS,
over the LAN).

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
conversation. Every 32k preset in `models-preset.ini` is therefore unusable
with it — not slow, not degraded, unable to answer one request.

128k is the smallest practical bucket. `claude-local.sh` refuses anything under
64k with a message that says so, rather than letting the router produce the
error above.

Claude Code also assumes a 200k window for model names it does not recognise,
which will silently mis-drive auto-compaction. Set it explicitly:

```
CLAUDE_CODE_MAX_CONTEXT_TOKENS=131072
```

**Cost note.** ~42k tokens of prefill at Laguna's ~1,850 tok/s is roughly 23
seconds before the first token of the first turn. llama.cpp reuses the cached
prefix, so this is a per-session and post-compaction cost, not per-turn.

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
[laguna-33B-A3B-128k]
alias = laguna-128k,claude-sonnet-5,claude-opus-5,claude-haiku-4-5-20251001
```

Verified: a `/v1/messages` request for `claude-sonnet-5` returns
`"model":"laguna-33B-A3B-128k"`. Aliases do **not** appear as separate entries
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

Every model on this box is text-only. A single image in context produces the
above, and Claude Code then **retry-loops** on it (`attempt 5/10`), so one
screenshot ends the session.

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

All from the MacBook, over the LAN, against the router:

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

## Choosing a model

Claude Code is an agentic loop: it rewards instruction-following and reliable
tool calls more than raw speed.

**Laguna is a poor default despite being the fastest.** It scored 27/50 on
`code-quality` and last on `cdn-freshness` (see README), and it shows here —
asked to reply with an exact token it instead declined and explained what it
was designed for. Correct tool calls, unreliable instruction-following.

Better picks already on disk:

* `qwen3.8-27B-128k` — `Q3_K_XL` v3, **35/50**, the strongest coder on disk
  that fits a 128k preset
* `qwen3-coder-80B-A3B-128k` — 34/50, the coding specialist
* `glm-4.7-flash-30B-A3B-128k` — MoE, ~43 tok/s at 32k, not yet suite-tested

`laguna-33B-A3B-q8-128k` over the Q4_K_M if Laguna is wanted anyway: identical
coding score, +25 points of library knowledge, still 30 tok/s.

---

## `claude-local.sh`

```bash
claude-local list                        # what the router is serving
claude-local                             # default model, interactive
claude-local qwen3-coder-80B-A3B-128k    # switch model
claude-local --chrome                    # add Chrome DevTools, text-only
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
