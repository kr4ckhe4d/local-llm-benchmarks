# GSQ-RCO IQ3_S — Qwen3.8-27B from ISTA-DASLab

Measured 2026-09-26 on the 9800X3D box (RX 9070 XT, 16,304 MiB, ROCm, llama.cpp
b10463). The file is `ISTA-DASLab/Qwen3.8-27B-GSQ-RCO-GGUF`,
`Qwen3.8-27B-GSQ-RCO-IQ3_S-mtp.gguf` (12.1 GB), the size the card calls
"task-lossless". It is plain GGUF with a per-tensor quant-type assignment and
runs on the stock build unmodified.

**Verdict: not adopted.** Against `UD-Q3_K_XL-v3`, which the MTP presets
already run, it is 1 GB smaller, has twice the KL-divergence and is 18% slower
under MTP. The only thing it buys is VRAM headroom.

The sibling repo `Qwen3.8-Flash-Next-GSQ-RCO-GGUF` is 66-76 GB and does not fit
16 GB VRAM + 32 GB RAM at any of its sizes.

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
