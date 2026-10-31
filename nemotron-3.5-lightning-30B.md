# Nemotron 3.5 Lightning 30B-A3B — fastest generation measured here, weakest answers

Measured 2026-10-31 on the two cards (R9700 + 9070 XT, 48,928 MiB), llama.cpp
b11434 (`5e03bdd87`), the production `build/`. File is
`ggml-org/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-Q8_0.gguf` (31.3 GiB; byte
length checked against the remote `content-length`, 33,585,495,616 — no
published sha256 to verify against), with the repo's separate
`mtp-…-Q8_0.gguf` (2.1 GB) as the drafter. Raw output in
[`benchmarks/nemotron-3.5-lightning-30B-A3B-Q8_0/`](benchmarks/nemotron-3.5-lightning-30B-A3B-Q8_0/).

**Verdict: not adopted.** It generates faster than anything else this repo has
measured — 167 tok/s at 8 bits, 1.70x from its MTP drafter at 83% acceptance —
and 128K context costs only 2.7 GB more than 32K. It then spends all of that
thinking: **28,152 reasoning tokens on average** to write one stdlib function,
197,067 tokens across the 7-task suite, for 35/50 against Bolt's 39/50. Library
recall is 75% at Q8_0, where Qwen3.8-27B reaches 91-92% at *three* bits.

Raw tok/s is the wrong lens here. At 136 tok/s deep and ~28K tokens per answer,
a task costs ~3.5 minutes of generation. Being the fastest decoder in the repo
does not make it the fastest to an answer.

The architecture is `nemotron_h_moe` (128 experts, ~3B active, Mamba-2 + MoE +
select attention) and loads on the stock build with no patching.

---

## Speed — the one thing it wins

700-token probe from `throughput-test.py`, temp 0.0, n=3, ctx 32768, flags
`-lm dio -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 -np 1`.

| | prompt | generation | draft acceptance |
|---|---|---|---|
| no drafter | 602.00 +/- 2.30 | 98.44 +/- 0.08 | — |
| **MTP drafter** | 561.22 +/- 3.26 | **167.05 +/- 0.32** | **83.2%** (499/600) |

MTP is worth **1.70x**, and acceptance was 83.2% on all three runs — identical
to three decimal places, which is what greedy decoding on a well-matched drafter
should look like. For comparison in this repo: Qwen3.6 35B-A3B UD-Q6_K 72 tok/s,
Qwen3.8 27B UD-Q6_K + MTP 57, Gemma 4 31B dense Q6_K + MTP 52, Nemotron 3.5 Bolt
74B-A9B 55.4. Nothing else here is close, and this is 8-bit.

Note the drafter *costs* prefill (602 -> 561) and buys generation, the usual
trade. Generation falls to ~136 tok/s once the cache is deep (observed during
the 20-minute thinking run), not 167.

Unlike every GSQ-RCO file tried here, there is no slow small-batch path: this is
a K-quant-heavy Q8_0, so MTP verification at pp4/pp8 is not penalised.

## Fit

`fit.sh`, ctx 32768, same flags, MiB.

| ctx | | model | peak | free | GTT | tightest card |
|---|---|---|---|---|---|---|
| 32,768 | no drafter | 33,728 | 34,460 | 14,468 | +6 | 9070 XT 3,687 |
| 32,768 | + MTP drafter | 36,141 | 36,873 | 12,055 | +6 | 9070 XT 3,608 |
| 65,536 | + MTP drafter | 37,041 | 37,775 | 11,153 | +6 | 9070 XT 3,317 |
| **131,072** | + MTP drafter | 38,845 | 39,579 | **9,349** | +6 | 9070 XT 2,737 |

The drafter costs **2,413 MiB**, against Qwen3.8's in-file MTP at ~2,212-2,450
and DFlash2's ~1,710 plus ~630 MiB per server slot.

**`-lm dio` is required, not optional.** The weights are 31.3 GiB against 30 GB
of RAM, the same condition that made the mmap loader thrash on
Qwen3.8-Flash-Next (`gsq-rco.md`). Not re-tested under mmap here; the dio path
loaded without incident and there was no reason to reproduce a known failure.

**32K -> 128K costs 2,706 MiB**, drafter attached, no GTT spill at any size.
That is the Mamba-2 hybrid doing what it should: most layers carry no KV at all.
NVIDIA's card validates llama.cpp only to `-c 40960` and says "raise it as VRAM
allows" — on this hardware that ceiling is far too conservative, and 256K looks
plausible on the 9,349 MiB still free at 128K. **256K not fit-tested.**

## Probes

`run-suite.sh`, ctx 32768, MTP drafter attached, against Bolt measured the same
way (b11719, 2026-10-18).

| | Lightning 30B-A3B Q8_0 | Bolt 74B-A9B 24GB |
|---|---|---|
| code-quality | **27/50 (54%)**, 1/7 clean | 35/50 (70%), 2/7 clean |
| code-quality, thinking | **35/50 (70%)**, 1/7 clean † | 39/50 (78%), 4/7 clean |
| cdn-freshness | **27/36 (75%)**, 3/9 clean | 15/33 (45%), 0/9 clean |
| tool calling | single ok, parallel ok | single ok, parallel ok |

† `code-quality-thinking-t1-128k.txt`, at temperature 1.0 / top-p 0.95 and ctx
131072. Bolt's 39/50 is greedy at ctx 32768, so the two are **not strictly
comparable**; see below for why greedy could not be used here.

Tool calling is clean: one call for the single case, two for the parallel case,
both tokens resolved and summed correctly. No `force_nonempty_content` was
needed for these probes, though NVIDIA's card says coding agents want it.

### Library recall is a weights property, not a quant cost

`cdn-freshness` is the probe that discriminates at this level —
`dflash2-qat-q2.md` found it reads 91/92/92% across Qwen3.8-27B's 3- and 4-bit
tiers, then 67% at UD-Q2_K_XL and 33% at QAT-Q2_0. Lightning at **Q8_0** lands
at 75%:

| | |
|---|---|
| Qwen3.8-27B UD-Q3_K_XL-v3 | 92% |
| **Nemotron Lightning Q8_0** | **75%** |
| Qwen3.8-27B UD-Q2_K_XL | 67% |
| Nemotron Bolt 74B-A9B 24GB | 45% |
| Qwen3.8-27B QAT-Q2_0 | 33% |

So it sits between Qwen3.8-27B's 2- and 3-bit quants while carrying essentially
no quantisation damage of its own. It invented `recharts@2.12.3` and two
`@emotion` UMD paths identically on every one of three runs — stable, not
sampling noise. Better than Bolt's 45%, and still the family's weak axis.

### Thinking: two void runs before a valid one

It took three attempts to get a thinking score, and the two failures are worth
recording because both look like results and neither is one.

| run | ctx | max-tokens | temp | score | why |
|---|---|---|---|---|---|
| `code-quality-thinking.txt` | 32768 | 30,000 | 0.0 | 16/50 | **void** — budget-bound |
| `code-quality-thinking-t1.txt` | 32768 | 65,536 | 1.0 | 23/50 | **void** — context-bound |
| `code-quality-thinking-t1-128k.txt` | 131072 | 65,536 | 1.0 | **35/50** | valid |

In the valid run no task was truncated: peak generation per task was 30,852 /
35,368 / 45,106 / 18,813 / 32,125 / 27,645 / 7,158, all inside both the 65,536
budget and the 131,072 context. Every task answered; none scored 0.

**Run 1 was capped by `--max-tokens`.**

`code-quality-thinking.txt` reads 16/50, *below* the 27/50 non-thinking score,
with `glob_match` 0/8, `shlex_split` 0/7 and `csv_rows` 0/7 — and `csv_rows`
scored 7/7 clean without thinking. That is not a capability reading. Driver and
output: `thinking-diagnosis.py` / `.txt` in the model folder.

```
csv_rows    finish='length'  content=0ch      reasoning=107,896ch  completion_tokens=30000
glob_match  finish='stop'    content=3,603ch  reasoning= 79,657ch  completion_tokens=22395
```

`csv_rows` spent the entire 30,000-token budget inside the reasoning block and
emitted **no content at all**, so its 0/7 means "never answered". `glob_match`
answered on the diagnostic pass having scored 0/8 on the graded run under
identical greedy settings, so the graded run does not reproduce either.

`code-quality-test.py` already documents this in its `--temperature` help:
greedy decoding sends thinking models into loops that never terminate, naming
`glob_match` on Qwen3.8-Flash-Next at xhigh. 16/50 measures that.

The finding that survives is the token consumption itself: **~20-27K reasoning
tokens to reimplement `csv.reader` or `fnmatch`**, at temperature 0.0. NVIDIA's
card documents only thinking on/off for this model, no reasoning-effort levels;
that was not tested here. Bolt cleared the same
7 tasks inside the same 30,000-token cap and scored 39/50. NVIDIA's own guidance
asks for 65,536 output tokens on agentic work, so this is the model behaving as
designed — it is simply expensive.

**Run 2 was capped by the context, not the budget.** Raising `--max-tokens` to
65,536 while leaving `-c 32768` cannot work: prompt plus reasoning plus answer
must fit the context. Peak generation per task was 21,532 / 32,496 / 32,359 /
5,558 / 32,368 / 5,861 / 17,628 — three tasks stopping just under 32,768, with
truncation in the server log. The 65,536 budget was never reachable. Same three
tasks at 0, a different cause.

The one signal from run 2: `glob_match` went 0/8 -> 7/8 purely from leaving
greedy. The loop `code-quality-test.py` warns about is real on this model.

### What the valid run says

35/50 at temperature 1.0, against Bolt's 39/50 at temperature 0.0 — one sample
versus a reproducible score, so read the gap as "no better than Bolt", not as a
precise 4-check deficit. Lightning's *thinking* score equals Bolt's
*non-thinking* 35/50.

The cost is the finding. **197,067 generated tokens across 7 tasks, averaging
28,152 per single stdlib function**, at temperature 1.0 with a 45,106-token
worst case. Bolt cleared the same suite inside a 30,000-token cap. NVIDIA's own
guidance asks for 65,536 output tokens on agentic work, so the model is behaving
as designed — it is simply very expensive, and three of these seven tasks cannot
be served at all in a 32K context with thinking on.

## Not tested

* 256K context. 128K is fit-tested and ran the thinking suite; 256K is not.
* Generation and prefill at depth. Every throughput number here is the shallow
  probe; the only deep figure is the ~136 tok/s observed during the thinking
  runs, which is not a controlled measurement.
* A greedy thinking score. Temperature 0.0 loops on this model, so there is no
  reproducible thinking number to set beside Bolt's 39/50.
* `Q4_0` (18.9 GB) — the only other GGUF offered, legacy, no imatrix, no
  K-quants. KLD against the Q8_0 measured here would cost ~3 minutes of scoring
  plus the download and is the obvious next measurement.
* BF16 reference. At 63.2 GB it does not fit 48,928 MiB of VRAM and will not run
  CPU-side on 30 GB of RAM, so Q8_0 is the only available reference for this
  model.
* A real Claude Code session, which is what settled Qwen3.8-Flash-Next.
* Vision. No mmproj is published in the GGUF repo.
* `force_nonempty_content`, which NVIDIA's card says coding agents require.
