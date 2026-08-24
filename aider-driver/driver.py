#!/usr/bin/env python3
# Drives aider through the same task Cline and Claude Code ran, using aider's
# Python scripting API rather than the CLI: coder.run(with_message=...) called
# once per phase, in one persistent session, matching how a human would
# actually work with aider turn by turn -- since a suggested shell command's
# OUTPUT only becomes visible to the model on the *next* .run() call (aider
# does not auto-continue on shell output the way it does on --auto-test
# failures), each turn below is scoped to what the model can act on with what
# it has already seen.
import os, sys, time

os.environ["OPENAI_API_BASE"] = "http://127.0.0.1:8090/v1"
os.environ["OPENAI_API_KEY"] = "local"

PROJECT = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT)

from aider.coders import Coder
from aider.commands import Commands
from aider.io import InputOutput
from aider.models import Model

# THE actual reason no shell command ever produced real output in the first
# two runs, traced all the way into aider's own source (io.py confirm_ask):
#
#   if self.yes is True:
#       res = "n" if explicit_yes_required else "y"
#
# --yes-always / io.yes=True does NOT approve shell command execution --
# handle_shell_commands()'s "Run shell command?" prompt passes
# explicit_yes_required=True specifically, which flips a blanket "yes" into
# an automatic decline. This is deliberate safety design in aider (unlike
# Cline/Claude Code, --yes-always here does not let a script auto-approve
# arbitrary shell execution) -- but it is also why the model's suggested
# curl/date/python commands were detected correctly (confirmed via
# coder.shell_commands) and then silently declined every single time, with
# no error surfaced. The model's own conclusion -- "I can't run shell
# commands in this environment" -- was accurate for what it had actually
# experienced, just not for the reason it guessed.
# verify.sh's auto-test cycles worked throughout because --auto-test is a
# separate code path that does not go through this confirmation at all.
_orig_confirm_ask = InputOutput.confirm_ask
def _confirm_ask_always_yes(self, question, default="y", subject=None,
                             explicit_yes_required=False, group=None, allow_never=False):
    if explicit_yes_required and self.yes is True:
        return True
    return _orig_confirm_ask(self, question, default=default, subject=subject,
                              explicit_yes_required=explicit_yes_required,
                              group=group, allow_never=allow_never)
InputOutput.confirm_ask = _confirm_ask_always_yes

# /web's non-Playwright fallback scraper is broken on this box: two runs both
# saw it explode to ~2.55M tokens of context regardless of which URL was
# requested (the LiveCodeBench JSON once, an unrelated unpkg directory
# listing the next time), which permanently kills every later turn since
# aider has no compaction to recover from an oversized message the way Claude
# Code does. Telling the model not to use /web in the prompt did not work --
# it reached for /web again on the very next turn despite an explicit
# instruction to use curl instead. Disable the command structurally so the
# failure is impossible rather than hoped-against, same fix as blocking
# take_screenshot for the Claude Code run.
def cmd_web_disabled(self, args, return_content=False):
    self.io.tool_error(
        "/web is disabled for this session -- its scraper is broken on this "
        "box. Use a shell command (curl) instead."
    )
    return ""
Commands.cmd_web = cmd_web_disabled

MODEL_NAME = "openai/qwen3.8-27B-128k"

# The first run of this task wrote lcb_check.sh and lcb_openweight_report.py
# correctly, then never executed either one -- it only ever *edited* them as
# files, and later said "I can't run shell commands or download files from
# this environment... run these commands locally." That belief was accurate
# for what it had actually done (writing a file is not the same as invoking
# it), but wrong about the harness: a shell command written as a fenced code
# block in the reply DOES get auto-executed here, with real output shown on
# the next turn (confirmed separately: verify.sh's own auto-test cycles fired
# and were correctly used to fix two real bugs). It just never tried emitting
# one. Every turn below that needs a command run now says so explicitly and
# up front, rather than leaving it to be inferred.
EXEC_NOTICE = (
    "(Shell commands you write as a fenced ```bash code block in this reply "
    "ARE automatically executed in this environment, and the real output "
    "will be shown to you on your next turn. Do not just write a script and "
    "stop -- include the command to run it now, in this same reply. "
    "IMPORTANT: each LINE inside the ```bash block is run as its own separate "
    "command, not as one multi-line script -- there is no heredoc support and "
    "no shared state between lines. Never put multi-line Python (or any "
    "multi-line logic) directly inside a ```bash block. For anything beyond a "
    "single command, first create it as a FILE with a normal file edit (e.g. "
    "check.py), then run it with ONE single-line command in the ```bash block, "
    "e.g. `python3 check.py`.)\n\n"
)

TURN_1 = EXEC_NOTICE + """\
Establish today's actual date with a shell command (do not assume it), then \
download this URL to a local file with curl -- do NOT use the /web command \
or any HTML scraper for this; it is a large raw JSON file, not a web page, \
and dumping it whole into the chat would blow the context budget:

  curl -sS -o lcb.json https://livecodebench.github.io/performances_generation.json

Do not use the interactive leaderboard -- it requires authentication; this \
JSON does not. Never cat, print, or otherwise output the full contents of \
lcb.json into the chat -- it is tens of megabytes. Report the date, the \
downloaded file's size (wc -c lcb.json), and only its top-level structure via \
a targeted script, e.g.:

  python3 -c "import json; d=json.load(open('lcb.json')); print(list(d.keys())); [print(k, type(v).__name__, len(v)) for k,v in d.items()]"

and one sample entry from each top-level list (index [0] only, not the whole \
list)."""

TURN_2 = EXEC_NOTICE + """\
lcb.json is PER-QUESTION results, not a leaderboard: each entry under \
"performances" is one question's pass@1 for one model, keyed by the "model" \
field (matching "model_repr" in the "models" list). Compute each model's \
score by grouping on model and averaging.

Do NOT use a composite, aggregate, or "index" score -- this pass@1 average is \
the single benchmark.

Write a Python script that does this computation and prints every model \
ranked by score, then RUN IT NOW with a shell command in this same reply -- \
report the real, printed ranking, not a description of what the script would \
output."""

TURN_2B = EXEC_NOTICE + """\
Using the real ranked output above, identify which models are open-weight: \
publicly downloadable weights, not an API-only tier. A real huggingface.co \
link in the model's "link" field is a strong signal; a model whose link is \
not a real weights repository is not open-weight -- do not include it \
without being able to confirm downloadable weights. Exclude any model with \
no published score.

Select up to 10 such open-weight models, ranked by score. For each, using \
what you already know plus anything you can confirm, determine: total \
parameters, active parameters if MoE, approximate VRAM at 4-bit, and whether \
it fits in 16GB using this rule:
  - Dense: weights + KV cache + compute buffer + ~1GB reserve. Weights alone \
    reaching 16GB does NOT fit -- treat ~13GB of weights as the practical \
    ceiling.
  - MoE: experts can offload to system RAM, so total size matters far less \
    than active parameters; judge against system RAM instead.

Never invent, estimate, normalise, or use "(est.)" for a score. Edit your \
scoring script (or a metadata table/dict inside it) to record this data for \
the selected models, then RUN IT AGAIN NOW with a shell command in this same \
reply so the final filtered table is real, printed output -- not something \
you describe without having actually produced it. Report that final table: \
model, score, total params, active params, VRAM at 4-bit, fits 16GB, source \
URL for each."""

TURN_3 = EXEC_NOTICE + """\
Now the frontend dependencies. Use React and MUI (Material UI) v5 UMD \
builds from unpkg, plus Recharts for charts and Babel standalone for JSX (no \
build step, no bundler). MUI v5 requires @emotion/react and @emotion/styled \
as peer dependencies loaded as globals before it -- or use Recharts + plain \
MUI without emotion if you can confirm MUI's UMD build does not need it; \
check rather than assume.

Before deciding on any URL, use a shell command to fetch it with \
`curl -sI -L <url>` (the -L follows redirects) and confirm the final status \
is 200. Do not guess filenames, casing, or whether a library ships a .min \
build -- if unsure of a package's exact file layout, curl the package's \
directory listing on unpkg (the bare package URL, e.g. \
https://unpkg.com/recharts/ for the recharts package) and read the file names \
it lists, rather than guessing one. Run the actual curl commands now, in this \
reply, and report the real status you observed for each URL -- not what you \
expect it to be."""

TURN_4 = """\
Now build the dashboard, as four separate files each under 200 lines:
  index.html      shell and <script> tags only
  data.js         the dataset -- the REAL, printed table from two turns ago. \
Every entry must be one of the models that script actually printed, with the \
exact score/params/VRAM values it printed. If any field still says \
REPLACE_WITH_ACTUAL_DATA, REPLACE_WITH_DATE_FROM_..., or similar, that is a \
bug -- go back and use the real values from what was actually printed.
  components.jsx  chart components
  app.jsx         dashboard layout and render

Load the .jsx files with <script type="text/babel" src="...">. Use only the \
dependency URLs you confirmed return 200 in the previous turn.

Content required:
- Horizontal bar chart of the benchmark score, 0-100, sorted best first.
- Two donut charts using DIFFERENT datasets: "Parameter Scale Distribution" \
  and "Hardware Accessibility (fits 16GB VRAM)".
- A data table: model, score, benchmark, params, active params, VRAM, 16GB \
  fit, source link.
- MUI components: Paper, Table, LinearProgress, Chip, Tooltip -- use all \
  five somewhere in the UI, not just import them.
- Tooltips showing score, benchmark, parameters and VRAM -- verify the prop \
  you use actually reaches Recharts' Tooltip component (a custom function \
  passed to the wrong prop silently does nothing; check Recharts' own docs \
  for the correct prop name for custom tooltip content).
- Title, plus a caption naming the exact benchmark and the date retrieved.

This project is served on http://localhost:8000 and auto-verified in a real \
headless browser after every edit -- if the verification fails, you will see \
the console/network output and an explanation of what failed; fix it and the \
check will run again automatically."""

TURN_5 = """\
Final summary. State: the exact benchmark used and confirmation it is a \
single benchmark, not a composite; every model's source URL and confirmation \
nothing was invented or estimated; the exact date used and how you obtained \
it; which MUI components you actually used in the rendered UI, not just \
imported; and the current state of browser verification (pass or the \
specific remaining failures)."""

TURNS = [TURN_1, TURN_2, TURN_2B, TURN_3, TURN_4, TURN_5]

def main():
    t0 = time.time()
    io = InputOutput(yes=True)
    model = Model(MODEL_NAME)
    coder = Coder.create(
        main_model=model,
        io=io,
        # This model's registered default is "whole": the parser expects
        # every fenced block in a reply to be a full-file dump under a
        # preceding filename, and a bare ```bash shell-command block (no
        # filename) gets misread as a malformed file listing --
        # "No filename provided before ``` in file listing" -- even though
        # suggest_shell_commands correctly detects the same block a layer
        # below. "diff" format's SEARCH/REPLACE parser does not have this
        # conflict; confirmed by a smoke test with edit_format="diff" before
        # this run.
        edit_format="diff",
        fnames=["index.html", "data.js", "components.jsx", "app.jsx"],
        auto_commits=False,
        suggest_shell_commands=True,
        test_cmd="./verify.sh",
        auto_test=False,  # only turned on for the Build turn -- see below
        stream=False,
        # THE actual root cause of the /web blowup, not just the model
        # reaching for /web itself: detect_urls=True (aider's default) scans
        # every message sent to the model -- including these scripted phase
        # instructions -- for literal URLs and auto-scrapes any it finds via
        # the same broken cmd_web before the model even sees the prompt. Both
        # poisoning events trace to a URL sitting in this driver's own turn
        # text (the LiveCodeBench URL in TURN_1, an example unpkg URL in
        # TURN_3), not to anything the model chose to do.
        detect_urls=False,
    )
    # verify.sh checks the RENDERED DASHBOARD. Turns 1-3 (research, scoring,
    # dependency checks) edit unrelated files (lcb.json, notes, etc) -- if
    # auto_test were on for those, every such edit would trigger a guaranteed,
    # irrelevant verify.sh failure (no dashboard exists yet), burn one of only
    # 3 reflections, and derail the model into debugging a page it was never
    # asked to build yet. Confirmed by a smoke test: an edit to a throwaway
    # smoke.txt file triggered exactly this. Scope it to the Build turn only.
    BUILD_TURN_INDEX = TURNS.index(TURN_4) + 1  # 1-based position, robust to reordering
    for i, turn in enumerate(TURNS, 1):
        coder.auto_test = (i == BUILD_TURN_INDEX)
        print(f"\n{'='*80}\nDRIVER: starting turn {i}/{len(TURNS)}  auto_test={coder.auto_test}  (+{time.time()-t0:.0f}s)\n{'='*80}", flush=True)
        coder.run(with_message=turn)
        print(f"\nDRIVER: finished turn {i}  (+{time.time()-t0:.0f}s)", flush=True)
    print(f"\nDRIVER_DONE  total={time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    main()
