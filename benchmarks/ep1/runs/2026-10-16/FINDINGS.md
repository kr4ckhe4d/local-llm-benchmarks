# Ep 1 findings, measured 2026-10-16 (for the script writer)

Everything below was measured in one session on 2026-10-16, on the same software:
llama.cpp build 11434 (commit 5e03bdd87), ROCm 7.2.4, kernel 7.2.9-2-cachyos,
Ryzen 7 9800X3D, 32 GB DDR5-6000, RX 9070 XT (16,304 MiB) + Radeon AI PRO R9700
(32,624 MiB). The router and Strata were stopped for the whole run.

Method: `benchmarks/ep1/run_ep1.py`. Speed is the repo's 700-token code probe,
median of 3, temperature 0, thinking off (`preset_probe.py`). Memory is `fit.sh`
with a 2,560-token probe, per card. Real depth is `depth_presets.sh`: one
128,025-token prompt, then the answer. Every number has a log in this folder
(`<key>.txt` and `logs/<key>/`).

Card names, never indexes: llama.cpp `ROCm0` = 9070 XT, `ROCm1` = R9700.

**The recorded numbers the script uses were on this same llama.cpp build
(11434).** Today's reruns land within 0-4% of them (table at the end), so the
script's "older software" caveat applies only to the DDR4/single-card rows and
the 58.12 twist row, not to the b11434 rows.

---

## 1. The control: gpt-oss-20b, 32K (fits any one card)

| Tier | `--device` | tok/s | Free on the card(s) used | Log |
|---|---|---|---|---|
| 16GB, 9070 XT alone | ROCm0 | **134.98** | 3,502 MiB | gptoss-rocm0.txt |
| 32GB, R9700 alone | ROCm1 | **142.37** | 20,380 MiB | gptoss-rocm1.txt |
| 48GB, both, layer split | ROCm0,ROCm1 | **128.40** | 24,410 / 10,918 MiB | gptoss-both.txt |

- **Splitting costs 9.8%** against the R9700 alone (128.40 vs 142.37). The
  recorded result was -10% (132.92 vs 147.10). Confirmed.
- **The 9070 XT alone is 5.2% slower than the R9700 alone** on a model that fits
  both (134.98 vs 142.37). The script's prediction was "≈142, matching the
  R9700"; that was wrong. Same Navi 48 chip and memory bandwidth on paper. One
  visible difference: the 9070 XT also drives the desktop (it showed ~420-580 MiB
  in use with nothing loaded). The cause was not measured, so say "slower" and
  not why.
- The appended `--device` does override the preset's own `device = ROCm1`: on
  the ROCm0 run the R9700 showed 32,567 MiB free (unused).

## 2. Qwen3.6-35B-A3B UD-Q6_K (MoE, 29.3 GB file, 40 expert layers)

### The 16GB wall

On the 9070 XT alone with no offload, llama.cpp tried to put **27,425 MiB** on
the 16 GB card and stopped at once:

```
cudaMalloc failed: out of memory
failed to allocate ROCm0 buffer of size 28756986368
llama_model_load: error loading model: unable to allocate ROCm0 buffer
```
(log: `logs/q36-fit-32768-ROCm0-ncmoe0.txt`, a good raw terminal moment.)

Smallest offload that fits with ≥1 GiB free on the 9070 XT:

| Context | `--n-cpu-moe` (expert layers on CPU) | Expert layers on GPU | 9070 XT free |
|---|---|---|---|
| 32K | **22** of 40 | 18 | 1,119 MiB |
| 128K | **24** of 40 | 16 | 1,055 MiB |

More than half the experts have to live in system RAM on the 16 GB card.

### Speed on every tier

| Config | 32K tok/s | 128K tok/s | Free at 128K (9070 XT / R9700) |
|---|---|---|---|
| 9070 XT alone, offload (22 / 24 layers on CPU) | **44.58** | **43.36** | 1,055 / unused |
| Both cards, same offload ("the twist") | 44.09 | 42.87 | 13,817 / 18,820 |
| **R9700 alone, no offload** | **78.44** | **78.44** | unused / 2,725 |
| Both cards, no offload (the preset as written) | 71.72 | 71.75 | 4,293 / 11,718 |

- **The big step is 16GB → 32GB: +76% at 32K, +81% at 128K** (44.58 → 78.44,
  43.36 → 78.44). That is removing the CPU offload.
- **When the model fits one card, one card beats the split by ~9%** (78.44 vs
  71.72 / 71.75), the same effect as gpt-oss.
- **Both cards (no offload) vs the 9070 XT with offload: +61% / +65%.** This is
  the comparison the script's "second GPU" story was built on; the R9700 alone
  does better.
- **Speed is flat from 32K to 128K** with no offload (78.44 both; 71.72 vs
  71.75), in an empty context. See depth below for the catch.

### The twist did not reproduce

The script's 8:15 section says the old offload preset got slower on two cards
(58.12 → 53.02, Q4_K_M, recorded on different software). Same-day, same file,
same offload: **44.58 → 44.09 at 32K and 43.36 → 42.87 at 128K, -1.1% both
times**, which is noise. Spreading an offloaded preset over two cards neither
helps nor (measurably) hurts. Either drop the twist or reframe it as "adding a
card does nothing while the experts are still on the CPU".

### Prediction check: R9700 alone

The reviewed script predicted Qwen3.6 Q6 would not fit the R9700 alone, even at
32K, from its two-card footprint (~32.5 GB). **Wrong: it fits at 32K (4,089 MiB
free) and at 128K (2,725 MiB free).** A split costs each card its own compute
buffers, so the two-card total overstates what one card needs. If the
prediction is kept on screen, show it failing.

## 3. Qwen3.8-27B UD-Q6_K, 128K (dense, 22.0 GB file)

| Config | MTP | tok/s | Draft acceptance | Free | Log |
|---|---|---|---|---|---|
| Both cards | on | **56.30** | 84.2% | 6,808 / 12,461 MiB | q38-both-mtp.txt |
| R9700 alone | on | **55.78** | 84.2% | 5,805 MiB | q38-rocm1-mtp.txt |
| R9700 alone | off | **24.06** | n/a | 7,375 MiB | q38-rocm1-nomtp-fixed.txt |
| 9070 XT alone | on | **does not fit** | | | q38-rocm0-mtp.txt |

- **For a dense model the second card adds nothing to speed**: 55.78 alone vs
  56.30 split (+0.9%, noise). What it adds is room, and at 128K Q6 does not
  even need it (5.8 GB free on the R9700).
- **MTP is worth 2.3x** (24.06 → 55.78) and costs about 1.6 GB of VRAM (7,375 vs
  5,805 MiB free).
- **The 9070 XT alone cannot hold it**: a 22 GB file on 16 GB.
- `q38-rocm1-nomtp.txt` (55.79, 84.2%) is **invalid** and is kept only as a
  record: appending `--spec-type none` did not turn MTP off; the preset's
  `spec-type = draft-mtp` still applied. The valid run removes that line from
  the preset (`q38-rocm1-nomtp-fixed.txt`, no draft lines in its server log).

## 4. Real 128K depth (both cards)

| Preset | Prefill (128,025 tok) | Generation at depth | Empty context (above) | Kept | Draft at depth |
|---|---|---|---|---|---|
| Qwen3.6 UD-Q6_K | 3,194 tok/s (~40 s) | **36.91** | 71.75 | **51%** | n/a |
| Qwen3.8 Q6 + MTP | 761 tok/s (~2.8 min) | **21.93** | 56.30 | **39%** | 50.7% (84.2% empty) |

- "Flat with context" is true only in an empty context; filled to 128K the
  MoE keeps about half its speed and the dense model about 40%.
- **MTP gets weaker deep in context**: acceptance falls from 84% to 51%.
- Peak VRAM at depth: Qwen3.6 20.9 / 12.1 GB, Qwen3.8 20.2 / 9.6 GB
  (R9700 / 9070 XT).

---

## 5. The 48GB case: Flash-Next on Strata (measured after the main run)

Every model above fits the R9700 alone, so the main run has no result where
both cards win. Strata (Qwen3.8-Flash-Next IQ3_XXS, 200K context, same day) is
that result. `benchmarks/strata-tuning/one_vs_two.py`, results in
`one-vs-two.json`; method as the tuning sweep (cold 29K-token prompt, six
1,000-token answers, temperature 0, thinking off).

| | Prompt reading | Generation | Code | Prose |
|---|---|---|---|---|
| Both cards (tuned) | 1,756 / 1,774 tok/s (two runs) | 93.9 / 96.9 | ~136 | ~75 |
| R9700 alone | 1,566 tok/s | **86.2** | ~105 | ~74 |

- **Both cards: +11% generation, +13% prompt reading, +31% on code**, prose level.
- Not a dramatic tier jump: the R9700 alone still keeps 95-99.6% of expert
  lookups in VRAM thanks to Strata's adaptive cache. The second card's extra
  room mainly speeds code, where the pipelined split also helps.
- So "48 GB never beat 32 GB" is false for Flash-Next. It holds for the models
  in sections 1-3 only.

## What this means for the episode

1. **The headline should be the bigger card, not the second card.** Going from
   16 GB to 32 GB removed the CPU offload and was worth +76-81% on Qwen3.6.
   Splitting across both cards was **~9-10% slower** than the R9700 alone for
   every model that fits one card (gpt-oss, Qwen3.6), and level for the dense
   Qwen3.8.
2. **So what is the 48 GB for?** Flash-Next on Strata (section 5) is the one
   measured case where both cards beat the R9700 alone: +11% generation, +31%
   on code. Every other model here fits one card and runs faster on it.
3. **Drop or reframe the twist** (section 2): -1%, not -9%.
4. **Fix two predictions on screen**: the 9070 XT is ~5% slower than the R9700,
   not equal; Qwen3.6 Q6 does fit the R9700 alone.
5. **The "16GB wall" shot is real**: the 27,425 MiB allocation failure, then 22
   of 40 expert layers pushed to the CPU.
6. **Room, not speed, for dense models** holds exactly (55.78 vs 56.30), and the
   MTP 2.3x is a clean number for the next episode.

## Against the recorded numbers (same llama.cpp build 11434)

| What | Recorded | Today | Diff |
|---|---|---|---|
| gpt-oss-20b, R9700 alone | 147.10 | 142.37 | -3.2% |
| gpt-oss-20b, both cards | 132.92 | 128.40 | -3.4% |
| Qwen3.6 Q6, both, 128K | 71.99 | 71.75 | -0.3% |
| Qwen3.6 Q6, 128K depth | 36.95 | 36.91 | -0.1% |
| Qwen3.6 Q6, 9070 XT free at 128K (both) | 3,996 | 4,293 | +297 MiB |
| Qwen3.8 Q6 + MTP, both, 128K | 56.84 | 56.30 | -1.0% |
| Qwen3.8 Q6, 128K depth | 21.85 | 21.93 | +0.4% |

gpt-oss reads ~3% lower today on both configs, so its *split costs 10%*
finding is unchanged; the absolute numbers moved (kernel went from 7.2.9-1 to
7.2.9-2 since; not investigated). Use today's numbers on screen.
