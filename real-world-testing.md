# Real-World Testing — agentic coding through Cline

`README.md` measures what the hardware can hold and how fast it runs. This file
measures whether the models can actually **do a job**: research live data, build
something, find their own bugs, and fix them without a human in the loop.

Everything here was run on the box described in the README's hardware section,
against `switch-model.sh router` on `llama.cpp b10463` (`7c35571e5`).

---

## Headline: feedback beats capability

The README's output-quality section records the same models producing charts
that rendered blank — invalid SVG, 404'd script tags — with **no model aware
anything was wrong**. Those runs were one-shot, through a chat UI, with no way
to observe the result.

Given a shell, a Python interpreter and a browser console, the same models
behave differently. **Muse Glimmer is the clean demonstration.** Its dependency
check returned:

```
200 200 404 404
```

Two `@emotion` URLs wrong — the same class of guess that shipped silently in
the one-shot runs. It caught them on its own verification step, reasoned toward
the correct `/dist/…umd.min.js` path, and corrected **before writing the file**.

Nothing about the model changed. What changed is that it could **check its
work**. That is a statement about harness design, not about model capability,
and it is the main thing this file records.

---

## Setup

**Cline → Settings → API Provider**

| Field | Value |
|---|---|
| Provider | OpenAI Compatible |
| Base URL | `http://192.168.4.228:8090/v1` |
| API Key | any non-empty string (llama.cpp ignores it) |
| Model ID | a router preset, e.g. `qwen3-coder-80B-A3B-128k` |

**`.clinerules`** in the project root holds the durable rules. Cline injects it
on every request, so compaction cannot eat it — which is what cost Gemma its
task constraints mid-session before the file existed. Only the task itself
("Build the dashboard per the rules") goes in the chat.

**chrome-devtools MCP**, in `cline_mcp_settings.json`:

```json
{
  "mcpServers": {
    "chrome-devtools": {
      "transport": {
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "chrome-devtools-mcp@1.2.0"]
      }
    }
  }
}
```

`command` must be `npx` with the package in `args`. A shell-style
`"command": "--"` produces `spawn -- ENOENT`, which reads like a missing
dependency rather than a config error.

**Serve over localhost, not `file://`.** External JSX will not load from
`file://` — Babel fetches it by XHR and the browser blocks that as cross-origin:

```bash
cd <project> && python3 -m http.server 8000
```

**Disable idle sleep while working.** Presets launch with
`--sleep-idle-seconds 900`; after 15 idle minutes Cline's next request pays a
full cold reload and may time out:

```bash
SLEEP_IDLE=-1 ~/llama.cpp/switch-model.sh router
```

---

## The task

Research the top 10 open-weight coding LLMs from a published benchmark, then
build a React + MUI dashboard that renders them — with a verification phase that
requires fetching every CDN URL and reading the browser console before declaring
success. The full prompt lives in `.clinerules`; its structure is four phases:

1. **Research** — live search, one benchmark, primary sources only, no invented values
2. **Dependencies** — fetch every script URL and confirm HTTP 200 before writing it
3. **Build** — separate files under 200 lines each, served over localhost
4. **Verify** — read the console via MCP, fix, re-check until clean

---

## Results

| Model | Preset | Found source unaided | Outcome |
|---|---|---|---|
| Gemma 4-26B-A4B | `gemma4-26B-A4B-128k` | **yes** | 6/6 scripts resolved incl. both `@emotion` peer deps; console clean; correct date via tool call |
| Qwen3-Coder-Next 80B | `qwen3-coder-80B-A3B-128k` | no — needed the URL | completed autonomously in ~40 min; 10 models; correct open-weight filtering |
| Muse Glimmer 30B | `muse-glimmer-30B-64k` | **yes** | wrote a correct aggregation script; caught its own `@emotion` 404s; rendered first try |
| GPT-OSS-20B | `gpt-oss-20b-A3.6B-32k` | no — needed the URL | **failed** — `peg-native` parser error, see below |
| Qwen3.8-27B | `qwen3.8-27B-128k` | n/a — chose SWE-bench | scraped the leaderboard out of the DOM via the browser MCP (in progress) |

### The scores corroborate across models

Three models independently produced the same LiveCodeBench figures, and two of
them computed the aggregate themselves from the published per-question file:

```
DeepSeek-R1-0528  84.4    Qwen3-235B-A22B                80.4
OpenReasoning-32B 81.0    OpenCodeReasoning-Nemotron-1.1 78.5
EXAONE-4.0-32B    80.9    DeepSeek-V3                    49.5
```

That file is **per-question results, not a leaderboard** — each entry is one
question's `pass@1`. Getting a model's score means grouping by model and
averaging. Muse Glimmer wrote that aggregation explicitly and landed on the same
numbers as the others, which is about as good a correctness check as is
available without a reference implementation.

---

## Dependency URLs: the failure the verify phase fixes

Every model here wrote correct React and MUI code and got the **script tags**
wrong. The library APIs were not the problem; the URLs were.

Under Cline with the verification phase:

| Model | Result |
|---|---|
| Gemma 4 | **6/6 resolved**, including both `@emotion` peer deps, identified unprompted |
| Muse Glimmer | guessed `/umd/…production.min.js` for `@emotion`, hit `404 404`, corrected to `/dist/…umd.min.js` before writing |

Compare the README's one-shot runs, where the same class of wrong guess was
written straight into the file and the page rendered blank with no error.

**This failure is fixable**, and you do not have to supply the URLs. Requiring
an *observed* HTTP status per URL turns a silent 404 into something the model
has to notice and correct. The rule that does the work:

> Before writing any `<script src>`, FETCH each URL and confirm it returns
> HTTP 200. Do not assume a status you have not observed. Do not assume a
> library ships a `.min` build. Read the library's browser/UMD docs for peer
> dependencies that must exist as globals first.

A verified working set, for reference:

```
https://unpkg.com/react@18/umd/react.production.min.js
https://unpkg.com/react-dom@18/umd/react-dom.production.min.js
https://unpkg.com/@babel/standalone@7/babel.min.js
https://unpkg.com/@emotion/react@11/dist/emotion-react.umd.min.js
https://unpkg.com/@emotion/styled@11/dist/emotion-styled.umd.min.js
https://unpkg.com/@mui/material@5/umd/material-ui.production.min.js
```

The non-guessable fact in there: **MUI v5 needs both `@emotion` packages loaded
as globals first**, and emotion's UMD lives at `/dist/…umd.min.js`, not the
`/umd/…production.min.js` shape most libraries use. Gemma identified this
unprompted; Muse guessed wrong and caught it. (The README records the
equivalent trap for Recharts, which ships no `.min` UMD build at all.)

---

## Rules that exist because something broke

These accumulated across both the one-shot runs in the README and the Cline runs
here; the rule is what matters, not which harness exposed it.

| Rule | The failure it prevents |
|---|---|
| One benchmark family, never a composite | A model chose "BenchAlign", a 437-benchmark composite that reads like a single score |
| Primary sources only — no aggregators or roundups | Five of ten scores once cited a tunneling-service blog |
| Never invent, estimate, or label "(est.)" | StarCoder2 appeared with `SWE-Bench (est.)` |
| Establish the date by tool call | A chart claimed "2026-08-26", ten days ahead |
| Open weights only, downloadable | Charts listed Qwen Max/Plus and Mistral Large, all API-only |
| Exempt the in-browser Babel warning | It can never be fixed; "console must be clean" otherwise loops forever |
| Also check `list_network_requests` | A 404'd script can throw nothing at all — the page is just blank |
| Practical VRAM ≈ 13GB of 4-bit weights | Models marked 16.0–16.4GB as "fits in 16GB", ignoring KV and compute buffer |

---

## Known issues

**GPT-OSS-20B cannot currently be driven through Cline.** It fails with
`The model produced output that does not match the expected peg-native format`
— the same parser class documented in the README's tool-calling section, which
breaks and gets fixed per model. Independently reported by other users. Two
things narrow it: a **single-turn tool call through the API works fine** (HTTP
200, correct `tool_calls`), and updating does not help — `7c35571e5` contains
per-model fixes for LFM2 and Muse Glimmer but nothing for GPT-OSS.

Record it as a **harness limitation, not a model limitation**.

**Cline's editor tool fails on large files.** `Editor input too large`, then a
fallback to rewriting the whole file, which fails the same way. Two mitigations:
split the output into files under 200 lines, and tell the model up front to use
a terminal heredoc for anything larger.

**Compaction eats the task prompt.** Gemma reported its instructions truncated
mid-run and asked for them again. Anything that must survive the whole session
belongs in `.clinerules`, not the chat.

---

## Limits of this file

One task, one client, five models, one run each. Nemotron-3-Nano and
Devstral have not been run through Cline at all — their entries in the README
come from one-shot testing and are not comparable to anything here. It shows that a feedback loop
changes outcomes dramatically and that two distinct failure classes exist with
different fixes. It is **not** a coding benchmark: no controlled scoring, no
repeats, and the task rewards research and dependency handling more than
algorithmic reasoning.
