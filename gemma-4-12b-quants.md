# Gemma 4 12B: BF16 vs Q8_0 vs Google's QAT Q4_0

Measured 2026-11-20 on the R9700 alone (`-dev ROCm1`), llama.cpp build 12165
(4b77dee05), 256K context, f16 KV, MTP drafting. Three files of the same
model:

| file | size | source |
|---|---|---|
| `gemma-4-12B-it-BF16.gguf` + BF16 MTP head | 22.2 GiB | ggml-org/gemma-4-12B-it-GGUF |
| `gemma-4-12B-it-Q8_0.gguf` + Q8_0 MTP head | 11.8 GiB | ggml-org/gemma-4-12B-it-GGUF |
| `gemma-4-12b-it-qat-q4_0.gguf` (+ the Q8_0 MTP head) | 6.5 GiB | google/gemma-4-12B-it-qat-q4_0-gguf |

**Q8_0 is the one to run.** It is BF16 within noise on every quality probe,
generates 2.1x faster and leaves 13 GB of the card free. The QAT Q4_0 is a
further 15% faster but is clearly worse: 25x the drift from BF16, a whole
code task lost to a missing comma split, and a fifth of its library URLs
dead.

## Speed and memory

`run-suite.sh`, 700-token code answer, temperature 0, n=3 after warmup (the
three runs per file agree within 0.2 tok/s).

| | generation | MTP acceptance | VRAM on the R9700 at 256K |
|---|---|---|---|
| BF16 | 49.9 tok/s | 77.7% | 30,229 MiB of 32,624 |
| Q8_0 | 104.3 tok/s | 79.1% | 19,160 MiB |
| QAT Q4_0 | 120.1 tok/s | 61.4% | 13,728 MiB |

Generation tracks file size, as it should on a bandwidth-bound card: BF16 to
Q8_0 halves the bytes and doubles the speed. QAT Q4_0 halves them again but
gains only 15%, because Google ships no MTP head: it runs with the Q8_0
model's head, and acceptance drops from 79% to 61%. A QAT-matched head exists
(`Janvitos/gemma-4-12B-it-qat-assistant-MTP-Q8_0-GGUF`, not tested).

QAT is not what makes it fast. A QAT file is small because it is Q4_0; the
training only decides how much quality survives the rounding.

## Fidelity: chat-format KLD against BF16

`benchmarks/chat-kld.py`: BF16 answers 32 chat prompts greedily, the other
two are teacher-forced along that answer, top-100 logprobs per position, 4,634
positions. A top-100 approximation that reads lower than `kld-test.sh`;
compare rows within this method only.

| vs BF16 | mean KLD | 99% KLD | same top-1 |
|---|---|---|---|
| Q8_0 | 0.0022 | 0.038 | 98.8% |
| QAT Q4_0 | 0.0542 | 0.913 | 94.6% |

For scale, the same method put Gemma 4 26B UD-Q4_K_M at 0.012 / 97.6% against
its Q8_0. QAT is not BF16 rounded: Google trained the checkpoint further with
4-bit rounding simulated, so its drift includes that training change as well
as quantisation error. It is still the distance from the BF16 model.

The wikitext `kld-test.sh` pass was run first and discarded: BF16 scored
PPL 530 on raw wiki.test (536 at `-c 2048`, so not a batching artifact), Q8_0
agreed on only 86% of top tokens, and QAT scored a *lower* PPL than BF16
(306). Instruction-tuned Gemma 4 does not model raw wikitext, the same
problem `chat-kld.py` was written for on the 26B in October. Its 26.7 GB base
file was deleted.

## Code quality

`code-quality-test.py`, 7 tasks / 50 checks, temperature 0, corrected prompts.

| run | BF16 | Q8_0 | QAT Q4_0 |
|---|---|---|---|
| router, thinking off (`router nothink`) | 35 | 36 (2026-11-06) | 25 |
| router, thinking on (budget 1024) | 27 | 28 (2026-11-06) | 33 |
| `run-suite.sh`, standalone server, thinking off | 35 | 37 | 21 |
| `repair` strategy, thinking off | 36 | 37 | — |

BF16 and Q8_0 differ by one check everywhere, and not in BF16's favour; the
misses land on different tasks, which is what noise on a 50-check probe looks
like. All three pass `csv_rows`, `add_months`, `parse_qsl` in most runs and
all three fail most of `urljoin`.

QAT is the odd one in both directions. Thinking off it loses `csv_rows` 7 -> 0:
its parser handles quotes and line ends but never splits on commas. In the
standalone suite the same task timed out. Thinking on it scores 33, the best
of the three, mostly because it did not lose a task to the budget cut that
cost BF16 `glob_match` (its whole answer was the word `thought`) and Q8_0
`shlex_split`. Repeating BF16's `glob_match` three times did not reproduce
`thought`: these budget-cut losses land on a random task per run. Temperature
0 is not deterministic through the router either: the first request of a set
gave a different answer from the next two.

**Repair barely helps Gemma.** The harness feeds the model's own failing
assert tests back for 2 rounds; on Qwen3.8-27B Q8_0 that is +7 (43/50). Here
it is +1 on both files, and every weak task still failed its own tests after
both rounds: Gemma's tests share its misreadings of the spec.

## Tool calling and library freshness

| | single / parallel tool calls | CDN URLs that resolve | clean runs |
|---|---|---|---|
| BF16 | pass / pass (3 calls) | 39/39 | 9/9 |
| Q8_0 | pass / pass (3 calls) | 39/39 | 9/9 |
| QAT Q4_0 | pass / pass (3 calls) | 33/42 (79%) | 3/9 |

## Files

* `benchmarks/gemma-4-12B-it-{BF16,Q8_0,qat-Q4_0}/`: `throughput.txt`,
  `tool-calling.txt`, `code-quality.txt`, `cdn-freshness.txt` (run-suite),
  `fixed-prompts/` (router runs, raw answers saved), `strategies/repair*`.
* `benchmarks/chat-kld/results.txt` and `run-gemma4-12B.log`.
* Presets: `gemma4-12B-bf16-vision-256k`, `gemma4-12B-qat-q4-vision-256k`
  next to the existing `gemma4-12B-q8-vision-256k`.
