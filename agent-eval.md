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

## Inkling-2-Mini, 2026-11-28: more passes, no false claims, twice the time

Same harness, tasks and limits, on the router's `inkling-2-mini-q8-128k` preset (Unsloth UD-Q8_K_XL, R9700 alone,
128K, `-ub 512`, the preset's sampling: temperature 1.0, top-p 1.0), router build `ad3ef916b`. "Thinking off" is not
quite off for Inkling: its template has no off switch, the preset asks for effort 0 and the router's thinking patch
gives it up to 1,024 tokens per turn, so it thinks briefly on every turn where Qwen3.8 writes none.

| | runs pass | tasks passed all 3 runs | false claims | correct when it says "done" | synthetic / real | turn limit | wall / run | tokens / run |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.8-27B (stock) | 42/63 (67%) | 11/21 | 4 | 37/41 (90%) | 26/30 / 16/33 | 22 | 132 s | 4.9K |
| Huihui-Qwen3.8-27B | 42/63 (67%) | 10/21 | 6 | 39/45 (87%) | 24/30 / 18/33 | 17 | 135 s | 4.4K |
| **Inkling-2-Mini Q8** | **47/63 (75%)** | **14/21** | **0** | **42/42 (100%)** | **30/30** / 17/33 | 20 | **270 s** | **12.8K** |

* **The gain is all on the synthetic repos** (30 of 30, where the Qwens dropped 4 and 6), including `slow-dedupe`
  3/3, which both Qwen models failed every time. On the real repos it is level with them: 17 of 33 against 16 and 18.
  Five runs is inside this eval's noise (about 6 of 63), so the overall lead is suggestive, not settled.
* **It never said "done" when it wasn't.** 42 claims, 42 passes. Every one of its 16 failures ran out of turns
  (or, once, lost the server; below) rather than ending with a wrong claim. On click `func-type-message`, where stock
  claimed done 3 times with the wrong reading of an empty error message, Inkling passed 3/3.
* **Where it is weaker:** click `default-map-nargs` 0/3 (both Qwens 3/3), tomlkit `multiline-comment` 0/3 (stock 2/3),
  and Python-Markdown 1/3 like stock.
* **It takes twice as long:** 283 minutes for the 63 runs against 139 for stock. It writes 2.6 times the tokens
  (12.8K a run against 4.9K) in fewer turns (25.4 against 27.1), and about three quarters of what it writes is its
  per-turn think. It generates at about the same speed as Qwen3.8-27B Q6 with MTP (49 tok/s in this run's log,
  against ~57 empty for the Q6), so the extra time is the thinking, not the engine.
* **One server crash.** On the last run (`tomlkit-sort-keys`, repeat 3, turn 42) the Inkling `llama-server` child
  segfaulted inside `libamdhip64` while launching a captured one-token graph (`ggml_cuda_graph_launch_chunk`), after
  about 4.7 hours of serving and ~800K graph reuses; the router reported `exited with status 1` and the run ended on
  an HTTP 500. It passed the other two repeats of that task, so the crash probably cost one pass. Not reproduced or
  diagnosed; it is the same family as the `hipGraphExecUpdate` segfault that made the branch capture graphs for
  one-token batches only.

Results: [`results/inkling-2-mini-q8/`](benchmarks/agent-eval/results/inkling-2-mini-q8/summary.txt). The one-task pilot
(`results/pilot-inkling/`) checked that Inkling's tool calls parse through this loop before the full run.

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
