# Running aider against the local router

aider is the third harness tested against this router, after Cline
([`real-world-testing.md`](real-world-testing.md)) and Claude Code
([`claude-harness.md`](claude-harness.md)). It is the odd one out
architecturally: no native tool-calling, no MCP, no JSON-schema-to-grammar
compilation. It parses plain-text diffs and plain-text shell-command
suggestions out of an ordinary chat completion. That difference is the whole
story here — it sidesteps every compatibility failure the other two harnesses
hit, and it introduces a different set of failures of its own, all traced to
source in this file.

Everything here was run 2026-08-24 against llama.cpp `b10463` (`7c35571e5`),
aider 0.86.2 (`uv tool install aider-chat`), model `qwen3.8-27B-128k` unless
noted.

---

## Compatibility: 11 of 11

The three models disqualified under Claude Code's native tool-calling
(`qwen3.8-27B`, `qwen3.8-27B-xxs`, `qwen3.5-9B-uncensored` — a chat-template
message-ordering conflict) and the one disqualified under both Cline and
Claude Code (`gpt-oss-20b` — a `peg-native` parser failure / grammar
compilation failure) all pass a basic file-edit smoke test under aider without
issue. Verified across every 128k preset on the router with a one-line bug
fix (`aider --model openai/<preset> --openai-api-base ... -m "fix the bug"`).

This is the direct payoff of aider's design: it never asks the model to
produce a JSON-schema-constrained tool call or match a specific structured
parser format. It asks for a unified diff or a full file in plain text, which
every chat-completions model handles natively — no grammar compilation, no
message-shape assumptions to violate.

---

## Driving it: the CLI's `--message` isn't enough for a multi-turn task

`aider --message "..."` is one-shot: it sends one message (plus up to
`max_reflections = 3` automatic follow-ups if `--auto-test`/`--auto-lint`
fail) and exits. Reproducing a Cline-style multi-phase task needs real
multi-turn state, so this used aider's Python scripting API instead:

```python
from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model

coder = Coder.create(main_model=Model("openai/qwen3.8-27B-128k"), io=InputOutput(yes=True), ...)
coder.run(with_message=TURN_1)
coder.run(with_message=TURN_2)   # same session, full history carried over
```

Each `coder.run()` call is a real turn in one persistent conversation —
this is the intended scripting interface, not a workaround.

---

## Gotcha 1: `/web`'s fallback scraper explodes context, with no recovery

```
litellm.BadRequestError: OpenAIException - request (2555413 tokens) exceeds
the available context size (131072 tokens)
```

`detect_urls=True` (aider's default) scans **every message sent to the
model** — including scripted driver instructions, not just the model's own
choices — for literal URLs, and auto-scrapes any it finds via `/web`'s
non-Playwright fallback. This happened twice, on two unrelated URLs (the
LiveCodeBench JSON once, an unrelated `unpkg.com` directory-listing page the
next run), both times ballooning to **~2.55 million tokens** regardless of
the actual page size — strong evidence the fallback scraper is returning
something like a fixed-size garbage blob rather than the real page content.

Telling the model not to use `/web` in the prompt did not help — it reached
for `/web` again on the very next turn. Aider has no compaction to recover
from an oversized message the way Claude Code does, so this silently killed
every subsequent turn for the rest of the session with no further errors,
just cascading "exceeds context size" failures.

**Fix — structural, not prompted:**

```python
os.environ["OPENAI_API_BASE"] = "http://127.0.0.1:8090/v1"  # unrelated
Coder.create(..., detect_urls=False)

def cmd_web_disabled(self, args, return_content=False):
    self.io.tool_error("/web is disabled -- its scraper is broken here.")
    return ""
Commands.cmd_web = cmd_web_disabled
```

Both together: `detect_urls=False` stops the auto-scan on driver-authored
text; overriding `cmd_web` stops it even if the model tries to invoke it
explicitly. Same category of fix as blocking `take_screenshot` for Claude
Code — remove the capability structurally rather than hope the model avoids
it.

---

## Gotcha 2: `--yes-always` does not approve shell commands — by design

This is the one that cost the most time, and the one most worth knowing.

Every "write and run a script" instruction produced a model that wrote the
script, correctly, and then **never executed it** — instead saying things
like *"I can't run shell commands or download files from this
environment... to complete this, run these commands locally."*

That read as model confusion. It wasn't. Traced into aider's own source
(`io.py`, `confirm_ask`):

```python
if self.yes is True:
    res = "n" if explicit_yes_required else "y"
```

`handle_shell_commands()`'s "Run shell command?" prompt passes
`explicit_yes_required=True` specifically. **`--yes-always` / `io.yes=True`
does not approve that prompt — it flips to an automatic decline.** This is
deliberate: aider will not let a blanket "yes" auto-approve arbitrary shell
execution, unlike Cline and Claude Code, where `--yes-always`-equivalent
settings do cover Bash. Confirmed directly: `coder.shell_commands` correctly
contained the model's `date -u` command (detection worked), but
`run_shell_commands()` silently declined to run it, no error surfaced
anywhere. The model's self-diagnosis was accurate for what it had actually
experienced — just not for the reason it guessed.

`--auto-test` was unaffected throughout, which is why `verify.sh` cycles
worked correctly the whole time and were genuinely used to fix real bugs —
`cmd_test()` doesn't route through this confirmation at all.

**Fix:**

```python
_orig = InputOutput.confirm_ask
def _always_yes(self, question, default="y", subject=None,
                 explicit_yes_required=False, group=None, allow_never=False):
    if explicit_yes_required and self.yes is True:
        return True
    return _orig(self, question, default=default, subject=subject,
                  explicit_yes_required=explicit_yes_required, group=group, allow_never=allow_never)
InputOutput.confirm_ask = _always_yes
```

Worth being honest about what this removes: a genuine safety rail that
exists specifically to keep a fully-automated aider session from running
arbitrary shell commands unattended. Bypassing it was necessary for this
comparison's entire premise — testing whether the model can get real command
output — and the commands here were research/read operations (`curl`,
`date`, `python3` scripts), not destructive ones. It is not something to
carry into a real unattended setup without separately deciding that
trade-off.

---

## Gotcha 3: one shell-command block = one line, no heredocs, no multi-line

```
Running import json
import: unable to open X server `' @ error/import.c/ImportImageCommand/350.
Running d = json.load(open('lcb.json'))
/bin/sh: -c: line 1: syntax error near unexpected token `('
```

`handle_shell_commands()` does `commands_str.strip().splitlines()` and runs
**every line as an independent `run_cmd()` invocation**. A multi-line Python
block inside a ` ```bash ` fence gets torn apart line by line and each line
executed alone as its own shell command — `import json` genuinely tried to
run ImageMagick's `import` utility, `d = json.load(...)` is a shell syntax
error, and so on down the block. No heredoc support, no shared state between
lines.

Not fixable at the harness level — this is inherent to how commands are
parsed out of the response. The fix is instructional, and it worked
completely once stated explicitly: never put multi-line logic directly in a
` ```bash ` block; write it to a file first (a normal file edit), then run it
with one single-line command (`python3 script.py`). Confirmed working
end-to-end after this instruction: `Applied edit to rank_models.py` →
`Running python3 rank_models.py` → real, correct output back in context.

---

## Gotcha 4: `edit_format="whole"` can misread a shell-command block as a broken file edit

```
The LLM did not conform to the edit format.
No filename provided before ``` in file listing
```

`qwen3.8-27B`'s registered default `edit_format` is `"whole"`, which expects
every fenced block in a reply to be a complete file dump under a preceding
filename line. A bare ` ```bash ` shell-command suggestion — correctly
formatted per aider's own `shell_cmd_prompt` guidance, and correctly detected
by `suggest_shell_commands`'s separate logic — gets misread by the `"whole"`
format's own parser as a malformed file listing missing its filename. The
model tried several workarounds itself (different fence styles, no fence at
all) and reasoned about the conflict accurately, but none of its own
adjustments could resolve it, because removing the fence just moves the
failure to the *other* side: `suggest_shell_commands`'s detector specifically
requires a fenced block, so an unfenced command is never picked up either.
There is no way to satisfy both parsers' requirements on the same text.

**Fix:** override the model's default with `edit_format="diff"` in
`Coder.create()`. Diff format's SEARCH/REPLACE parser does not share this
ambiguity — confirmed via a smoke test before committing to the full run.

---

## A fifth, smaller thing: model and test-cmd can collide on the same port

Mid-diagnosis, while correctly working out that Recharts needed a
`window.PropTypes` global, the model tried to start its own
`python3 -m http.server 8000` — apparently assuming it needed to bring up the
dev server itself — and collided with `verify.sh`'s already-running instance:

```
OSError: [Errno 98] Address already in use
```

Not fatal, but it burned response budget on a crash mid-reflection at exactly
the point the model was about to apply the correct fix. Worth stating
explicitly in the task prompt that a server is already running, next time.

---

## The task result, twice

Same task as Cline and Claude Code ran (`clinerules` in this repo): research
LiveCodeBench scores from the live JSON, verify CDN dependencies, build a
React dashboard, verify it renders clean in a browser. Full detail on attempt
1 below; attempt 2 is the "does an explicit close-the-loop turn fix it"
follow-up.

### Attempt 1 (before gotcha 2 was known): correct diagnosis, nothing executed

The model wrote `lcb_check.sh` and `lcb_openweight_report.py` — genuinely
correct content — then, because of gotcha 2, never got real output back for
either. `data.js` shipped as a literal placeholder
(`const MODELS = []; // REPLACE_WITH_ACTUAL_DATA`), and the final summary
said so honestly rather than inventing numbers: *"I can't run shell commands
or download files from this environment... I cannot state the exact date."*
Total time: 20.3 minutes — fast because it did not do the work, not because
it was efficient.

Two structural aider bugs surfaced and were fixed during this attempt
(gotchas 1 and part of the diagnosis for gotcha 2), plus a parser artifact: a
stray file got created named after a fragment of the model's own bolded
prose (`Browser verification**: Currently **FAILING**...`), containing the
error text as its "content" — a smaller cousin of Cline's `peg-native`
failures, from the same underlying cause as gotcha 4 (the edit-format parser
misattributing a piece of prose as a file listing).

### Attempt 2 (gotchas 2-4 fixed, explicit "run it now" turns added): real data, broken frontend

With the confirmation gate patched, `edit_format="diff"`, and explicit
per-turn instructions to execute scripts immediately rather than just write
them, the closed loop worked. `rank_models.py` ran for real; its output is
independently verifiable — every score in `data.js` matches a direct
recomputation from the raw JSON to 4 decimal places, spot-checked across 7
models. `EXAONE-4.0-32B` and `XBai-o4-medium` were both correctly excluded as
not open-weight (both link to `wenxiaobai.com`, not a real weights repo) —
the same judgment call the Claude Code run independently reached.

But the frontend is worse than attempt 1's, in a different way:

* **Zero MUI usage**, despite the task explicitly requiring Paper, Table,
  LinearProgress, Chip, and Tooltip. Not an oversight — the model checked
  `@mui/material@5`'s bare unpkg URL, correctly found it resolves to a CJS
  Node build rather than a browser UMD global, and excluded MUI entirely
  rather than use something that wouldn't work. That conclusion is
  half-right: the bare package URL genuinely isn't a UMD build, but there is
  a working UMD subpath (`@mui/material@5.18.0/umd/material-ui.production.min.js`)
  that the Claude Code run found and used successfully. A real, honestly-reported
  research gap, not fabrication or laziness.
* **The page does not render at all.** `#root` has zero children. Recharts'
  UMD build needs `window.PropTypes` (from the `prop-types` package) as a
  global before it loads; that dependency was correctly identified and even
  `curl`-verified (200) during the Build turn's `--auto-test` reflection
  loop — the model's own diagnosis, mid-loop, was exactly right — but
  `max_reflections = 3` ran out before the actual one-line `<script>` fix
  ever got applied to `index.html`. The model spent its three auto-fix
  cycles on correct-but-slow diagnosis (including the port-collision
  detour above) rather than reaching the edit.

The final summary is fully honest about both gaps — states plainly that the
MUI requirement is not met and quotes the exact remaining console errors
verbatim, rather than claiming success. Independently reverified with a
direct browser check: confirmed `#root` children = 0, confirmed the exact
same two errors (`reading 'oneOfType'`, `reading 'BarChart'`) plus a
downstream React error #130 from rendering undefined components.

### The three-way scoreboard

| | Cline | Claude Code | aider |
|---|---|---|---|
| Model compatibility | ~5/6 | 7/11 | **11/11** |
| Failure class | native tool-call parser format | grammar compile / message order | turn-boundary + confirmation-gate mismatches |
| This task, data layer | mixed (Nemotron fabricated) | correct, verified | correct, verified (attempt 2) |
| This task, frontend | rendered, minor bugs | rendered, minor bugs (dead tooltip, missing 1 component) | **did not render at all** |
| Wall time | 40-70 min | 75 min | 20 min (broken) / 11.4 min (real data, broken UI) |

aider wins decisively on raw compatibility — nothing here is disqualified by
a protocol quirk. But getting a real task through it took five structural
fixes that a human driving aider interactively would never hit, because a
human naturally supplies the "now run it" nudge, notices when the model says
it can't run shell commands and pushes back, and would have caught the
prop-types gap by watching the browser directly instead of budgeting exactly
3 auto-fix cycles. The gap between "aider's mechanism can do this" and "a
scripted stand-in for a human successfully drives it through this specific
task" turned out to be substantial, and closing most of it still left a
frontend regression neither of the earlier two harnesses produced.

---

## Using it: two different answers depending on who's watching

The four fixes above split cleanly by whether a human is present to answer
aider's own prompts.

**Interactive** — a human at the terminal, approving things as they come up
— only needs two of the four, and both have real CLI flags:

```bash
aider-local.sh                           # default model, interactive
aider-local.sh qwen3.8-27B-128k          # pick a model
```

which is `aider --model openai/<preset> --no-detect-urls --edit-format diff`
against the router underneath. `--no-detect-urls` is gotcha 1's CLI-level
fix. `--edit-format diff` is gotcha 4's. Gotcha 2 (`--yes-always` not
covering shell commands) is not a bug in this mode at all — aider just asks
"Run shell command?" and a human answers it, same as any other confirmation.
Gotcha 3 (one line per shell command, no heredocs) has no flag; it's a
standing thing to know, documented in `aider-local.sh --help`.

**Unattended** — `--yes-always`, nobody watching, the same situation
`aider-driver/driver.py` was built for — needs gotcha 2's fix too, and that
one has no CLI flag; it requires monkeypatching `InputOutput.confirm_ask`
before invoking aider, which means the Python scripting API, not the CLI.
`aider-local.sh --yes-always ...` will silently hit gotcha 2 for any task
that needs real shell output. Use `aider-driver/driver.py` as the template
for that case instead — copy its four patches near the top of the file.

## `aider-driver/`

The scripted driver behind attempt 2 above — six turns, all five fixes,
`verify.sh` as `--test-cmd` scoped to the Build turn only. That scoping is a
sixth gotcha not detailed in its own section above: `--auto-test` fires on
*any* edit, including unrelated research-phase files, which burns reflections
on a guaranteed-irrelevant failure (there is no dashboard yet). Confirmed by a
smoke test where editing a throwaway file triggered a `verify.sh` failure
about a page that was never the subject of that turn. Fixed by toggling
`coder.auto_test` on only for the Build turn, off everywhere else.

```bash
cd aider-driver
python3 driver.py         # writes index.html, data.js, components.jsx,
                           # app.jsx, lcb.json, rank_models.py into this dir
```

Requires the router reachable at `127.0.0.1:8090` (edit `OPENAI_API_BASE` in
the script for a different host) and `chrome-devtools-mcp` fetchable via
`npx` (used by `verify_browser.py`, the `--test-cmd`). Re-running reuses
whatever files already exist in the directory — `rm -f *.html *.js *.jsx
lcb.json rank_models.py` first for a clean run, the same reset performed
between every attempt in this file.
