# GSQ-RCO IQ3_S — Qwen3.8-27B from ISTA-DASLab

Measured 2026-09-26 on the 9800X3D box (RX 9070 XT, 16,304 MiB, ROCm, llama.cpp
b10463). The file is `ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF`,
`Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` (12.1 GB), the size the card calls
"task-lossless". It is plain GGUF with a per-tensor quant-type assignment and
runs on the stock build unmodified.

**Verdict: not adopted.** Against `UD-Q3_K_XL-v3`, which the MTP presets
already run, it is 1 GB smaller, has twice the KL-divergence and is 18% slower
under MTP. The only thing it buys is VRAM headroom.

The sibling repo `Qwen3.8-Flash-Next-GSQ-RCO-GGUF` did not fit the single card.
With the R9700 its Q2_0 does, and it was tried on 2026-10-06; see
[Qwen3.8-Flash-Next](#qwen38-flash-next-gsq-rco-q2_0) below. Also not adopted.

---

## Fidelity — KLD against a Q8_0 reference

`kld-test.sh`, 200 chunks at `-c 512`, wikitext-2, identical to the BF16 runs
except for the reference. Output in `benchmarks/q8ref/`.

| | Size | Mean KLD | Median KLD | Same top-1 | PPL(Q)/PPL(base) |
|---|---|---|---|---|---|
| UD-IQ4_XS-v3 | 14.3 GB | **0.0182** | 0.0075 | **94.07%** | 1.0069 |
| UD-Q3_K_XL-v3 | 13.1 GB | 0.0265 | 0.0109 | 92.89% | 1.0171 |
| **GSQ-RCO IQ3_S** | 12.1 GB | 0.0529 | 0.0228 | 89.67% | 1.0204 |

GSQ-RCO moves the output distribution twice as far as Q3_K_XL-v3 and changes
the top-1 token 1.5x as often. The 99th-percentile KLD is 0.548 against 0.277,
so the tail is twice as heavy too, not just the mean.

### Why the reference is Q8_0, and why that is safe

The BF16 pass does not fit this box any more. `kld-test.sh`'s recipe ran it
CPU-only in 16m49s at 54.9 GB peak RSS, on 64 GB of RAM. With 32 GB the 55 GB of
weights page from disk through mmap on every pass: memory pressure 38% `full`,
one core busy, 213 MiB/s off the NVMe, and no batch of 4 chunks completed in
11 minutes. The estimate for 200 chunks was 4-5 hours, so it was stopped.

`Qwen3.8-27B-Q8_0.gguf` (unsloth, sha256 `a680f44a…e348`) at `-ngl 34 -t 8`
builds the same 200-chunk base in ~8 minutes, most of it writing 25.3 GB of
logits.

The substitution is checked, not assumed. Re-scoring the two quants that
already have BF16-referenced numbers:

| | vs BF16 (2026-08-21) | vs Q8_0 (2026-09-26) | shift |
|---|---|---|---|
| UD-IQ4_XS-v3 mean KLD | 0.01789 | 0.01816 | +1.5% |
| UD-Q3_K_XL-v3 mean KLD | 0.02627 | 0.02650 | +0.9% |
| UD-IQ4_XS-v3 same top-1 | 94.08% | 94.07% | — |
| UD-Q3_K_XL-v3 same top-1 | 92.94% | 92.89% | — |

`PPL(Q)` is bit-identical across both runs (6.903572 and 6.834680), so the
scoring side is deterministic and only the reference moved. Q8_0's own
distance from BF16 adds about 1% to each number and leaves the ordering alone.
The GSQ-RCO figure can be read against the existing BF16 table directly.

The Q8_0 base is kept at `~/llama.cpp/kld/qwen3.8-27B-q8_0.kld`, so scoring
another Qwen3.8-27B quant costs ~3 minutes. The BF16 weights were deleted
again, since they are no use on 32 GB.

---

## Speed — slower under MTP, for a kernel reason

700-token probe from `run-suite.sh`, `32k-mtp` preset flags (`-ub 512`, q4_0
KV), both files back to back. Output in
`benchmarks/q8ref/qwen3.8-27B-GSQ-RCO-IQ3_S/throughput.txt`.

| | Q3_K_XL-v3 | GSQ-RCO IQ3_S | |
|---|---|---|---|
| no drafter | 29.32 | 28.60 | −2.5% |
| MTP | **67.96** | 55.99 | **−17.6%** |
| draft acceptance | 86.8% | 87.0% | |
| VRAM peak, MTP | 14,729 MiB | 14,103 MiB | −626 |

The Q3_K_XL-v3 row reproduces the preset's recorded 29.52 → 69.14.

Acceptance is identical, so the drafter is not the difference. The target model's
forward pass is, and only when it is batched. `llama-bench` by batch size:

| | pp1 | pp2 | pp4 | pp8 |
|---|---|---|---|---|
| Q3_K_XL-v3 | 26.70 | 49.06 | 89.29 | 128.08 |
| GSQ-RCO IQ3_S | 26.60 | 49.46 | **70.03** | **105.46** |

The two are level at one and two tokens and 18-22% apart at four to eight, which is
where MTP verification runs. GSQ-RCO spends its budget differently: 2.1 GB of
IQ3_XXS and 1.1 GB of IQ2_S/IQ2_XS/IQ2_XXS, against 0.9 GB and 0.6 GB in
Q3_K_XL-v3. Those types have the slow small-batch path on ROCm.

---

## Reading the model card against this

The card's evidence is task scores: AIME25 at 100.00, LiveCodeBench v6 at
85.71, GPQA-Diamond 0.51 below BF16. Two reasons they do not transfer here:

* **The comparison is against UD-IQ3_S**, not the UD-Q3_K_XL-v3 this repo
  runs. It is a 1 GB-larger file with a different type mix.
* **The benchmarks are small.** AIME25 is 30 problems, so one problem is 3.3
  points. This repo already found that coarse task probes do not order quants:
  `code-quality` ranked IQ4_XS last and Q2_K_XL first (see
  `dflash2-qat-q2.md`). KLD is measured per token over 51,000 scored tokens,
  and its error bars are about 1% of the value.

The card may well be right that GSQ-RCO beats UD-IQ3_S at equal size. That
comparison was not measured here.

## Where it could still earn a place

The 1 GB it saves is the same 1.1 GB that stops IQ4_XS from creating the MTP
draft context (see `models-preset.ini`). At 32k with MTP it peaks 626 MiB
below Q3_K_XL-v3 under identical flags. That is on the shallow probe, so add
it to Q3_K_XL-v3's measured 321 MiB at depth, not to the probe's own figures.
MTP at q8_0 KV or at 48k might fit where Q3_K_XL-v3 does not. **Neither was fit-tested.** Even if they fit, it would be
trading 2x KLD and 18% speed for context, which the existing 64k/128k presets
already provide without a drafter.

---

## The smaller sizes: IQ3_XXS and IQ2_S (2026-10-02)

The repo also ships `IQ3_XXS-mtp` (10.4 GB) and `IQ2_S-mtp` (9.6 GB), 2.7 and
3.5 GB under UD-Q3_K_XL-v3. That is more than the ~2.45 GB the MTP drafter
costs, so the question was whether they buy MTP past its 32K ceiling, and at
what price. Measured on llama.cpp `a868c3e3c`, with Q3_K_XL-v3 re-run beside
them as the same-build control. Driver and raw output:
`benchmarks/raw/gsq-rco-small/`.

**Verdict: not adopted, and not the right file for MTP at depth either.** Both
do unlock MTP at 64K and 128K, but at 3.8-5.2x the KLD, and Unsloth's own
files of the same size are more faithful.

| | UD-Q3_K_XL-v3 | GSQ-RCO IQ3_XXS | GSQ-RCO IQ2_S |
|---|---|---|---|
| Size | 13.1 GB | 10.4 GB | 9.6 GB |
| Mean KLD vs Q8_0 | **0.0264** | 0.0996 (3.8x) | 0.1376 (5.2x) |
| Same top-1 | **92.89%** | 86.28% | 83.93% |
| tg, no MTP, shallow | 32.66 | 34.63 (+6%) | 36.01 (+10%) |
| tg, no MTP, 16.8K deep | 25.34 | 26.59 | 27.31 |
| tg, MTP, shallow | **70.00** | 56.21 (−20%) | 58.37 (−17%) |
| tg, MTP, 16.8K deep | **63.79** | 53.04 (−17%) | 52.52 (−18%) |
| Draft acceptance, shallow / deep | 84.6 / 85.7% | 82.0 / 84.5% | 85.2 / 82.4% |
| MTP reach | 32K, q4_0 | **64K q8_0** (2,186 free), 128K q4_0 † | **64K q8_0** (2,992 free), **128K q4_0** (2,195 free) |

tok/s, 700-token probe, `32k-mtp` flags (`-ub 512`, q4_0 KV). The control
reproduces both its earlier scores: KLD 0.0264 vs 0.0265 on `7c35571e5`, MTP
70.00 vs 70.05 this morning. IQ2_S at 128K q8_0 loads with 185 MiB free,
under the 281 line, so it is not a fit. IQ3_XXS at 128K q8_0 fails outright.

† Fits, but the row is suspect: it ran straight after the failed q8_0 load
and saw a 101 MiB desktop baseline and GTT −149, so the desktop had been
evicted. `model=14,802` suggests ~1,100 MiB free on a normal desktop.

### Same kernel story as IQ3_S, only more so

Without a drafter the smaller files are 6-10% *faster*, simply by being
smaller. With MTP they are 17-20% slower, for the reason found for IQ3_S:
`llama-bench` puts them level or ahead at one and two tokens and 19-25% behind
at four to eight, where MTP verifies.

| | pp1 | pp2 | pp4 | pp8 |
|---|---|---|---|---|
| Q3_K_XL-v3 | 25.5 | 54.5 | **94.1** | **136.0** |
| GSQ-RCO IQ3_XXS | 32.3 | 58.9 | 70.9 | 110.7 |
| GSQ-RCO IQ2_S | 28.0 | 60.3 | 71.8 | 110.2 |

(`-r 3`; pp1 carries ±6-16 of noise, pp4/pp8 ±7-11.)

### Unsloth's files of the same size are better

KLD from this repo's earlier runs (BF16 reference, which the Q8_0 reference
reproduces to within 1.5%):

| File | Size | Mean KLD | Same top-1 |
|---|---|---|---|
| Unsloth UD-IQ3_XXS | 10.9 GB | **0.0589** | **89.28%** |
| GSQ-RCO IQ3_XXS | 10.4 GB | 0.0996 | 86.28% |
| Unsloth UD-Q2_K_XL | 9.8 GB | **0.0889** | **87.02%** |
| GSQ-RCO IQ2_S | 9.6 GB | 0.1376 | 83.93% |

Unsloth's Q2_K_XL is 0.6 GB *smaller* than GSQ-RCO IQ3_XXS and still closer
to the reference. So if MTP at 64K is worth a fidelity cut, the cut should be
made with an Unsloth file. UD-Q2_K_XL is also K-quant-heavy, so it may avoid
the slow IQ small-batch path that costs GSQ-RCO its MTP speed. **That is
untested**: neither Unsloth file has been run under MTP. Both KLD figures
postdate Unsloth's 2026-08-19 re-quantisation (measured 2026-08-21 and
2026-08-31), so they describe the files Hugging Face serves now.

---

## Qwen3.8-Flash-Next GSQ-RCO Q2_0

Tried 2026-10-06 on the two cards (R9700 + 9070 XT, 48.9 GB), llama.cpp
b11434. `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF`, `Q2_0/`, 66.4 GB in two
shards. Arch `qwen4exp`: 512 experts x 48 layers, 10 active, 176.9B total
(51.8B of it embeddings, mostly a per-layer n-gram table), ~6.7B active per
token. Q2_0 was picked over IQ2_XS for the publisher's 3.4x prefill at the
same task average; IQ3_XXS's 47 GB of weights would not leave room for KV.

**Verdict: not adopted.** One real Claude Code session (a WebGL landing page,
the same task as in `claude-harness.md`) finished, at clearly lower quality than
Qwen3.8-27B Q8_0. It was thorough but spent four rounds chasing a NaN that came
from a typo in its own test snippet. That matches the publisher's scores: 89.07
task average against 93.12 for BF16, LiveCodeBench v6 81 against 87. Preset
and files removed.

Not ruled out: the session ran at `reasoning-budget = 1024`, and several steps
thought for ~36 s, about 1,000 tokens at the rate it ran, so it was likely
being cut off. Q8 had the same cap. No speed probe or `cdn-freshness` was run.

### How it fits, for next time

The weights shard (37.6 GB) goes on the GPUs. The n-gram shard (28.8 GB) stays
on the NVMe, read one row per token with `--lazy-mode on`.

**Use `-lm dio`, not the model card's `-lm mmap`.** Under mmap the loader
prefetches every mapping (`prefetch_size = -1` in `init_mappings`), the n-gram
shard included, and on 32 GB of RAM that thrashed the page cache: 44.6 GB read
at ~300 MB/s, no "listening" in 600 s. `-lm dio -lzm on` loads in 11 s; the
lazy tensors are still mapped without mmap mode (`llama-model-loader.cpp`,
the `use_mmap || lazy.any()` branch).

`fit.sh`, `-lm dio -lzm on -fa on`, f16 KV unless noted, MiB free per card:

| ctx | flags | R9700 | 9070 XT | |
|---|---|---|---|---|
| 32K | auto split | 7,801 | 1,797 | fits |
| 32K | `-ts 13,35` | 5,517 | 4,080 | fits |
| 128K | auto split | 5,152 | **125** | too tight |
| 128K | q8_0 KV | 6,067 | 429 | too tight |
| 128K | `-ts 14,34` | 3,358 | 1,916 | fits |
| 128K | `-ts 13,35` | 2,623 | 2,650 | **fits, balanced** |
| 256K | `-ts 13,35` | | | spills to GTT |
| 256K | `-ts 13,35`, q8_0 KV | 910 | 1,091 | marginal |

`-ts` is 9070 XT (ROCm0) first. KV is small (12 of 48 layers have full
attention, 2 KV heads): 32K -> 128K costs ~4.3 GB.

The embedded chat template is Qwen3.8-27B's byte for byte, including the
late-system `raise_exception` that breaks Claude Code, so
`templates/qwen38-late-system.jinja` works unchanged. The file has no MTP
layer. Through the router, a Messages API tool-call probe returned a correct
`tool_use` in 7.7 s including the cold load.
