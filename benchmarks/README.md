# benchmarks/

Probe scripts, and one folder per model holding that model's raw output.

Everything here was measured on the machine described in the root `README.md`
(RX 9070 XT, 16,304 MiB, ROCm, llama.cpp `b10463`). The root README holds the
*conclusions*; this folder holds the evidence they were drawn from.

## Layout

```
benchmarks/
  run-suite.sh              driver -- runs the probes and writes into a model folder
  fit.sh                    VRAM fit measurement (has the GTT spill guard)
  needle-test.py            verbatim long-context recall
  semantic-recall-test.py   recall by meaning, against near-miss distractors
  tool-calling-test.py      native OpenAI `tools` path, single + parallel
  code-quality-test.py      coding quality, scored by executing the output
  cdn-freshness-test.py     library knowledge, scored by HEADing emitted URLs
  kld-test.sh               KL-divergence of a quant against an unquantised reference
  <model>/                  one folder per model, outputs written by run-suite.sh
```

Model folders are **generated, not hand-assembled**. A result you cannot
regenerate is a claim, not a measurement:

```bash
./run-suite.sh qwen3.8-27B-UD-IQ3_XXS-v3 Qwen3.8-27B-UD-IQ3_XXS-v3.gguf 196608 \
    "-ub 512 -b 2048 -fa on -ctk q4_0 -ctv q4_0"
```

Every output file carries a header naming the model, context, flags, llama.cpp
build and timestamp, so a file is interpretable on its own.

## What is in a model folder

| File | Probe | Written by |
|---|---|---|
| `throughput.txt` | 700-token code prompt, temp 0.0, n=3 | `run-suite.sh` |
| `tool-calling.txt` | single + parallel native tool calls | `run-suite.sh` |
| `code-quality.txt` | 50 differential checks vs stdlib | `run-suite.sh` |
| `cdn-freshness.txt` | 3 prompts x 3 runs, every URL HEADed | `run-suite.sh` |
| `needle-deep.txt` | verbatim recall near the context ceiling | by hand |
| `semantic-deep.txt` | semantic recall near the ceiling | by hand |
| `fit.txt` | VRAM sweep across contexts | by hand |
| `kld.txt` | KL-divergence vs the BF16 reference | `kld-test.sh score` |

The deep-recall probes are driven by hand because each costs ~12 minutes of
prefill at 190K and needs a depth chosen per model. Their files are the
captured run output, headed with the depth actually built — **both scripts
overshoot `--depth`**, `needle-test.py` by ~7.8% and `semantic-recall-test.py`
by ~17%, so the requested depth is not the measured one.

## The two probes that had to be rebuilt

Worth reading before trusting a number here.

**`code-quality-test.py` was useless in its first form.** It used
self-contained leetcode-style tasks — merge intervals, LRU, roman numerals —
and all three models scored **50/50**. Saturated, measuring nothing, exactly
like the needle probes at 32K. It only resolves because it now does
*differential* testing: the model reimplements a stdlib behaviour
(`fnmatch`, `shlex.split`, `urljoin`, `textwrap.wrap`, `csv.reader`,
`parse_qsl`) from scratch, and its function is compared against the real one
over edge cases plus a seeded random batch. Matching `urljoin` exactly is hard;
matching it on the happy path is easy; the gap is the score.

It is validated: with stdlib wrappers substituted for the model, all 7 tasks
score 50/50, so a failure belongs to the model and not to the checks.

**`cdn-freshness-test.py` had a scoring bug** that was found and fixed
mid-comparison. Bare-origin URLs are `<link rel=preconnect>` hints, not asset
loads, and legitimately fail a HEAD — scoring them punished *correct* markup
and cost one model two false failures per run. Now excluded via
`urlparse(url).path in ("", "/")`.

## Caveats that apply to every number here

* **Recall probes are saturated at 32K.** Every quant scores 5/5. They confirm
  nothing broke; they cannot rank models. Only the deep runs near the ceiling
  discriminate.
* **Coding scores are deterministic but narrow.** `temperature 0.0` is greedy,
  and re-runs reproduce check-for-check — so these are measurements, not
  samples. But the spread across three models is 4 checks in 50, and all three
  fail on the same near-floor tasks (`urljoin` dot-segments, `textwrap`
  collapsing, `shlex` double-quote escapes). A different task set could reorder
  the top two.
* **`code-quality-test.py` executes model-written code.** It runs in a temp
  directory under a wall-clock timeout, which is containment, not a sandbox.
* **Desktop VRAM drifts.** Baseline moved between 263 and 442 MiB during one
  session. `fit.sh` reports model-attributable VRAM (peak minus baseline) for
  this reason, and any row near the ceiling should be read from `loaded=`
  rather than `model=` — see the spill guard note in the root README.
