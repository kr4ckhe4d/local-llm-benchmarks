# agent-eval: agentic coding, graded by hidden tests

`code-quality-test.py` asks for one function in one shot. This asks a model to do the job a
coding agent is used for: read a repo it has never seen, reproduce a reported bug, change
the code, run the tests, and say when it is done. Then hidden tests decide whether it was.

Results and discussion: [`agent-eval.md`](../../agent-eval.md).

## How a run works

1. The task's repo is copied into a temp dir, `git init`-ed with one commit (no upstream
   history, so `git log` cannot reveal the fix), and mounted at `/work`.
2. The model gets an issue-style prompt and five native tools: `bash`, `read_file`,
   `write_file`, `edit_file`, `finish(status, summary)`. Turn limit 40 (50 for real repos),
   `max_tokens` 12288 per turn, thinking off unless `--think`.
3. Every shell command runs under `bwrap`: `/usr` and `/etc` read-only, no network, no
   `/home`, fresh `/tmp`, only `/work` writable, 120 s per command.
4. After `finish` (or the turn limit) the hidden tests are copied in and run in the same
   sandbox. Real-repo tasks first restore the upstream `tests/` tree, so editing a test
   cannot hide a regression.

Per run: **pass** (hidden tests pass; changing a visible test fails the run only where the
prompt says not to, as in `pricing-refactor-ci`), **claimed**
(`finish("done")`), **false claim** (claimed done, hidden tests fail), turns, tool calls,
malformed calls, tokens, wall time. Transcripts are in `results/<label>/runs/`.

## Tasks

| set | tasks | source |
|---|---|---|
| synthetic | 10 | small multi-file repos written for this: CSV quoting, DST scheduling, pagination, crash log, CLI feature, O(n²) dedupe, red CI after a refactor, a field through 4 modules, stale memo cache, SQL injection |
| real | 11 | real fixes from click (4), tomlkit (3), sqlparse (3) and Python-Markdown (1): the commit's parent is the task, the fix commit's tests are the hidden check |

Real tasks are found by `mine_real.py`, which walks a repo's recent history for commits that
change 1-2 source files with tests and keeps those whose tests fail on the parent and pass
with the fix. The prompt is written by hand from the fix and its tests, as a bug report.

**Every hidden assertion must trace to the prompt.** The first pilot failed a correct CSV
fix on thousands separators the prompt never mentioned; the prompt now states it. A hidden
test the prompt does not justify measures guessing, and turns honest work into "false claims".

Adding regression tests is what a good engineer does, so it is not penalised: the hidden
checks are separate files the model never sees, so editing the visible tests cannot game them.
The first full run counted two such runs as failures; `./agent_eval.py rescore <label>`
re-applies the current rule to recorded runs.

## Commands

```bash
uv venv --python /usr/bin/python3 .venv && uv pip install --python .venv/bin/python pytest
./agent_eval.py validate                  # every task: pristine fails, reference passes
./agent_eval.py run --model huihui-qwen3.8-128k --label huihui-qwen3.8-27B-q6 --repeats 3
./mine_real.py https://github.com/pallets/click --commits 300
```

`validate` must print `OK` for every task before a run means anything. It is how two of my
own hidden tests and two reference fixes were caught being wrong.

## Limits

* Python only, and pytest-checkable behaviour only.
* Real-repo checks run the fix commit's test files, not the whole suite (click's full suite
  takes over 5 minutes in the sandbox), so a regression elsewhere goes unseen.
* Upstream fixes from 2025-2026 may be in a model's training data. The synthetic tasks
  cannot be.
* One harness. A model that works well in Claude Code or Qwen Code but badly with these five
  tools would score low here.
