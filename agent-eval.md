# agent-eval: Huihui-Qwen3.8-27B against stock Qwen3.8-27B on 21 coding tasks

Measured 2026-11-22 on the two-card box in `README.md` (RX 9070 XT + R9700, ROCm),
llama.cpp `29b52d398`. Harness, tasks and transcripts:
[`benchmarks/agent-eval/`](benchmarks/agent-eval/).

`code-quality-test.py` asks for one function in one shot. That says little about the
model as a coding agent, which is how the 27B models are used here. agent-eval gives each
model a repo it has never seen and a bug report. The model has to reproduce the bug, change
the code, run the tests and say when it is done. Hidden tests then decide whether it was.

## Setup

* **Loop.** One small agent loop, the same for every model. It uses native OpenAI tool calls
  through llama-server and five tools: `bash`, `read_file`, `write_file`, `edit_file` and
  `finish(status, summary)`.
* **Limits.** 40 turns per task (50 for the real-repo tasks), `max_tokens` 12288 per turn,
  thinking off.
* **Sandbox.** Every command runs under `bwrap` with no network and no `/home`. Only the
  working copy is writable, and each command gets 120 s.
* **Tasks.** There are 21:
  * 10 synthetic: small multi-file repos written for this eval.
  * 11 real: actual bug fixes from click (4), tomlkit (3), sqlparse (3) and Python-Markdown
    (1). For each, the fix commit's parent is the starting repo and the fix commit's tests
    are the hidden check. `mine_real.py` keeps only commits whose tests fail on the parent
    and pass with the fix.
* **Fairness checks.**
  * `./agent_eval.py validate` passes on every task: each untouched repo fails its hidden
    tests and each reference fix passes them.
  * Every hidden assertion is stated or implied by the prompt.
* **Runs.** Each model does 3 repeats of all 21 tasks, 63 runs per model, at the model's
  sampling defaults (temperature 1.0, top-p 0.95, top-k 20).
* **Models.** Both use the 128K presets: q8_0 KV cache, MTP draft, `-ub 512`.
  * Huihui is `UD-Q6_K_XL` (24.8 GB).
  * Stock is `UD-Q6_K` (22.0 GB).

  Huihui's file keeps more tensors at Q8_0 (271 against 154), so if anything it is
  slightly the more precise of the two.

What each run records:

* **pass:** the hidden tests pass.
* **claimed:** the model called `finish("done")`.
* **false claim:** it claimed done, but the hidden tests fail.

Turns, tool calls, tokens and wall time are recorded too.

## Result: a tie

| | runs pass | tasks passed all 3 runs | false claims | correct when it says "done" | malformed calls | turns / run | wall / run |
|---|---:|---:|---:|---:|---:|---:|---:|
| Huihui-Qwen3.8-27B (abliterated) | **42/63 (67%)** | 10/21 | 6 | 39/45 (87%) | 0 | 26.0 | 135 s |
| Qwen3.8-27B (stock) | **42/63 (67%)** | 11/21 | 4 | 37/41 (90%) | 0 | 27.1 | 132 s |

Abliteration costs nothing this eval can see. With 63 runs, the 95% interval on 67% is
about ±12 points. Neither model made a malformed tool call in 126 runs.

The two models fail differently:

| | synthetic (30 runs) | real repos (33 runs) | false claims, synthetic / real | runs ended by the turn limit |
|---|---:|---:|---:|---:|
| Huihui | 24 (80%) | 18 (55%) | 5 / 1 | 17 |
| stock | 26 (87%) | 16 (48%) | 0 / 4 | 22 |

* **Huihui's false claims are mostly on the small synthetic repos** (5 of its 6). In each
  case it said done without checking a case the prompt named:
  * slow-dedupe, twice: `[1, 2]` and `(1, 2)` treated as duplicate keys, although the
    prompt says duplicates are values that are equal under `==`.
  * pricing-refactor-ci: a discount rounded the wrong way (404 instead of 405).
  * stale-memo-cache: two calls with different arguments shared one cache entry, so one
    returned the other's stale result.
  * dst-scheduler: still wrong across daylight-saving transitions.

  The sixth is the click empty-message case described next.
* **Stock's false claims are all on click.**
  * `func-type-message`: it failed 3 of 3, each time claiming done. When a function used as
    a parameter type raised `ValueError("")`, stock passed on the empty message. The prompt
    says an error without a message should report the offending value instead. Stock read
    an empty string as "a message"; the test reads it as no message. That reading is
    arguable, but the prompt names the case.
  * `help-hint-shadowed`: failed 1 of 3, claiming done.
* **Stock ran out of turns more often** (22 runs against 17). Those runs neither pass nor
  claim; they fail honestly.

## Per task

| task | kind | Huihui | stock |
|---|---|---:|---:|
| config-crash-log | synthetic | 3/3 | 3/3 |
| csv-quoted-fields | synthetic | 3/3 | 3/3 |
| dst-scheduler | synthetic | 2/3 | 2/3 |
| logsum-date-filter | synthetic | 3/3 | 3/3 |
| notes-search-injection | synthetic | 3/3 | 3/3 |
| paginated-export | synthetic | 3/3 | 3/3 |
| pricing-refactor-ci | synthetic | 2/3 | 3/3 |
| slow-dedupe | synthetic | **0/3** | **0/3** |
| stale-memo-cache | synthetic | 2/3 | 3/3 |
| task-priority-field | synthetic | 3/3 | 3/3 |
| click-default-map-nargs | click | 3/3 | 3/3 |
| click-func-type-message | click | 2/3 | **0/3** |
| click-help-hint-shadowed | click | 3/3 | 2/3 |
| click-usage-no-args | click | 3/3 | 2/3 |
| markdown-uneven-backticks | Python-Markdown | **0/3** | 1/3 |
| sqlparse-begin-end-split | sqlparse | **0/3** | **0/3** |
| sqlparse-cli-truncation | sqlparse | 3/3 | 3/3 |
| sqlparse-real-name-dotted | sqlparse | 2/3 | 3/3 |
| tomlkit-inline-table-delete | tomlkit | **0/3** | **0/3** |
| tomlkit-multiline-comment | tomlkit | 1/3 | 2/3 |
| tomlkit-sort-keys | tomlkit | 1/3 | **0/3** |

Three tasks beat both models on every run:

* **slow-dedupe.** It needs an O(n) dedupe that keeps `==` semantics for unhashable keys.
  The models either broke the semantics or stayed too slow: one run took 100 s for 200,000
  records, against a 5 s limit.
* **sqlparse-begin-end-split.** The fix is in statement splitting inside `BEGIN ... END`
  blocks.
* **tomlkit-inline-table-delete.** Deleting the middle key of an inline table leaves a
  `, ,` behind.

All three runs on the last two used the full 50 turns. These tasks are where a stronger
model would show.

The synthetic tasks turned out easier than the real ones: about 80-87% pass against about
50%. A first 10-task pilot of synthetic tasks alone scored Huihui 9/10. That is why the 11
real-repo tasks were added, and they now carry most of the spread.

## Grading fix during the run

The first grader failed any run that changed a visible test file. In 2 Huihui runs and
4 stock runs, the model added regression tests, or fixed a test it had added itself; the
hidden tests passed every time. Writing regression tests is good practice. The prompts
don't forbid it, and the model can't see the hidden test files, so editing the visible
tests can't game the score.

Changing a visible test now fails a run only where the prompt forbids it. That is
`pricing-refactor-ci` ("do not change them"), marked `tests_frozen = true`. All results
were regraded from the saved runs with `./agent_eval.py rescore <label>`. Under the old
rule the scores were 40/63 and 38/63.

## Partial runs, not comparable

Two Qwen3.5 models were started as calibration and stopped early. Both have since been
deleted from this PC.

* **Qwen3.5-9B-Uncensored Q8_0 (HauhauCS): 4 of 9 runs passed.** On the same 9 runs
  Huihui passed 8 and stock 7. It made no false claims and no malformed calls, but it ran
  out of turns on 7 of the 9. On click-func-type-message it spent its last dozen turns
  trying click option types and calling helpers that don't exist. It used 12.5K completion
  tokens per run, against 4.4-4.9K for the 27B models. So the eval does separate a weaker
  model.
* **Qwen3.5-27B-Uncensored Q6_K (HauhauCS): 7 of 8 runs passed**, with 1 false claim (CSV
  line breaks). Huihui passed 8 of the same 8 and stock 7. It had no MTP head, so runs
  took about 260 s.

## Limits

* **Statistics.** 3 repeats × 21 tasks. A gap under about 6 runs out of 63 is noise.
* **One harness, thinking off.** A model that works better in Qwen Code or Claude Code, or
  with thinking on, could score differently.
* **Python only**, and only behaviour pytest can check.
* **Partial test coverage.** Real-repo checks run the fix commit's test files, not the
  whole suite, so a regression elsewhere goes unseen.
* **Training data.** The upstream fixes date from 2025-2026 and may be in the models'
  training data. The synthetic tasks cannot be.
