# Real-World Testing — agentic coding through Cline

`README.md` measures what the hardware can hold and how fast it runs. This file
measures whether the models can actually **do a job**: research live data, build
something, find their own bugs, and fix them without a human in the loop.

Everything here was run on the box described in the README's hardware section,
against `switch-model.sh router` on `llama.cpp b10463` (`7c35571e5`).

---

## Headline: feedback beats capability

The same models, on the same hardware, with the same prompt:

| Harness | Outcome |
|---|---|
| Open WebUI | 4 models asked for a chart, **4 blank pages**, none of them aware |
| Cline + chrome-devtools MCP | models catch their own 404s *before* writing the file |

Nothing about the models changed. What changed is that they could **check their
work** — `curl` a URL and see `404`, run a script and read its output, read the
browser console.

Muse Glimmer is the clean demonstration. It guessed the same wrong `@emotion`
UMD paths that Devstral and Qwen3-Coder shipped blind, hit `404 404` on its own
verification step, and corrected before writing. Same wrong guess, opposite
outcome, and the only difference was being made to observe the status code.

**The bottleneck was never model capability, it was the absence of a feedback
loop.** That is a statement about harness design, not about the models.

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

## Two failure classes, and only one is fixable by prompting

**Geometry — a reasoning failure.** Asked for an SVG bar chart, Nemotron
computed `height="-45"`, negating the value instead of offsetting `y`. A
negative `height` on `<rect>` is invalid, so the element silently is not drawn:
axis, ticks and labels render, the bars are absent, nothing errors. It held
across 4 regenerations, both `temp 1.0` and `0.25`, and reasoning budgets of
1024 and 4096. Muse Glimmer needed seven attempts at the same chart and only
succeeded after abandoning SVG for CSS bars.

**No amount of information fixes this.** What fixes it is avoiding the maths:
ask for MUI components or CSS bars rather than hand-written SVG paths, and let
the browser own layout.

**Dependency URLs — a recall failure.** Every model wrote correct React and
library code and failed only on the script tags:

| Model | Scripts resolving | What broke |
|---|---|---|
| Qwen3-Coder-Next | 2/4 | invented `babel@7.23.0`; that package's last version is **6.23.0** |
| Devstral Small 2 | 3/4 | `Recharts.min.js` — no minified UMD exists in any version |
| Qwen3-Coder-30B Q8_0 | 0/1 | omitted React, ReactDOM and Babel entirely |
| Gemma 4 *(with verify phase)* | **6/6** | — |

**This one is fixable**, and you do not have to supply the URLs. Requiring an
*observed* HTTP status per URL turns a silent 404 into something the model has
to notice and correct. The rule that does the work:

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

Two non-guessable facts in there: **Recharts ships no `.min` UMD build**, and
**MUI v5 needs both `@emotion` packages loaded as globals first**. Emotion's UMD
lives at `/dist/…umd.min.js`, not `/umd/…production.min.js` — the wrong guess
two models made independently.

---

## Rules that exist because something broke

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

One task, one client, six models, one run each. It shows that a feedback loop
changes outcomes dramatically and that two distinct failure classes exist with
different fixes. It is **not** a coding benchmark: no controlled scoring, no
repeats, and the task rewards research and dependency handling more than
algorithmic reasoning.
