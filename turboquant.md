# TurboQuant KV-Cache Quantization — CachyPC

Measured 2026-08-25 on the RX 9070 XT (gfx1201, RDNA4, 16,304 MiB) described in
[README.md](README.md). Everything here is from this box; nothing is quoted
from the project's own claims without being re-measured.

**Verdict up front: do not adopt it. Measured by KL-divergence, `turbo2` costs
more distribution quality than the entire weight quantization of `Q3_K_XL`, and
`turbo3` is 2.5x worse than plain `q4_0`.** Keep `Q3_K_XL` + `q4_0` at 128k.

The capacity results are real and reproducible — `IQ4_XS` genuinely fits at
131,072 with `turbo2` where `q4_0` cannot allocate at all, and it passes 5/5
needle *and* 5/5 semantic at ~121k. It is still the wrong trade, because those
retrieval tests saturate and cannot see what KLD sees. **This file spent most of
its length recommending a configuration that the last measurement overturned.**
The history is kept deliberately: every intermediate claim looked well-supported
at the time.

| | Mean KLD vs f16 KV |
|---|---|
| `q8_0` | 0.000744 |
| `q4_0` | 0.003901 |
| `turbo3` | 0.009823 |
| `turbo2` | **0.030743** |
| *(reference: `Q3_K_XL-v3` **weights** vs BF16, from README.md)* | *0.0263* |

Treat TurboQuant as a **VRAM tool with a real and previously unmeasured quality
price** — not the free win the compression ratios suggest. If VRAM is the only
binding constraint and quality genuinely does not matter, it works. On this box,
at 128k, it does not pay.

---

## What TurboQuant is

A rotation-based vector quantizer from Google Research
([paper](https://arxiv.org/pdf/2504.19874), ICLR 2026). It applies a fixed
128x128 orthonormal Walsh-Hadamard rotation to each K/V vector before
quantizing, which Gaussianizes the coordinates so a fixed Lloyd-Max codebook
fits them well. The rotation is orthogonal, so dot products survive it and it
never has to be undone. No calibration set, no per-model training.

It is **not merged into llama.cpp** and shows no sign of being. Every mainline
attempt was closed unmerged — `TBQ3_0/TBQ4_0` (#21089), `TQ3_0` (#24049,
#24050), `Q4_T` (#23617), `E8_2` (#25352), "Merge turboquant" (#23962) — and
one (#21818) was closed tagged **"AI policy violation"**. There is now an
upstream PR (#23201) titled *"require explicit agreement for including external
code"* that reads as a direct response to the wave. Mainline discussion is
[#20969](https://github.com/ggml-org/llama.cpp/discussions/20969).

So the only way to run it is a fork.

## The fork under test

[`TheTom/llama-cpp-turboquant`](https://github.com/TheTom/llama-cpp-turboquant),
branch `feature/turboquant-kv-cache`, commit **`bd9bd1b`**.

Unlike the mainline PR wave, this one looks like a real project: 2,313 stars,
399 forks, MIT, multiple contributors landing reviewed PRs in the #300s with
tests, and internal docs that are honest about their own gaps — their
`docs/quality-benchmarks.md` opens with *"we have ZERO quantitative quality
data on the actual llama.cpp build."* That candour is the main reason it was
worth the build cycle.

**It is behind upstream, and that matters for cross-referencing.** Measured:
1,756 commits ahead / **165 behind** its own master, 300 files changed. It
reports `ggml 0.18.1` against the `build/` tree's `0.20.1`. So numbers here are
**not** directly comparable to the `b10463` figures in README.md — which is why
every comparison below uses the fork's own `q4_0` as the control, same binary,
same run.

### The types it adds

| Name | Enum | Bits/value | vs f16 | Stored on disk? |
|---|---|---|---|---|
| `turbo2` | `GGML_TYPE_TURBO2_0` (43) | 2.0 | 6.4x | No — runtime KV only |
| `turbo3` | `GGML_TYPE_TURBO3_0` (44) | 3.25 | 4.9x | No — runtime KV only |
| `turbo4` | `GGML_TYPE_TURBO4_0` (47) | 4.25 | 3.8x | No — runtime KV only |
| `TQ3_1S` / `TQ4_1S` | 45 / 46 | 3 / 4 | — | **Yes — weight types** |
| `Q8_CR` / `Q5_CR` / `Q6_CR` | 48 / 49 / 50 | — | — | **Yes — weight types** |

**Type-ID collision is a live hazard.** Upstream's enum currently ends at
`Q2_0 = 42` with `GGML_TYPE_COUNT = 43`; the fork claimed 43-50 starting
exactly where upstream's count stood at fork time. Upstream's next new type
will be 43 and will collide with `TURBO2_0`.

For the KV types that is a recompile annoyance, because nothing is persisted.
For the weight types it is a data trap: **GGUF stores the integer type id**, so
files quantized to `TQ4_1S = 46` would be silently misread if a sync forces
renumbering. Practical rule for this box: **use the `turbo2/3/4` KV types
freely, do not invest in `TQ*_1S` / `*_CR` quantized model files.**

---

## Build

Same recipe as the ROCm build in README.md, different tree — this does **not**
touch `~/llama.cpp`:

```bash
git clone --depth 50 --branch feature/turboquant-kv-cache \
  https://github.com/TheTom/llama-cpp-turboquant.git ~/llama-turboquant
cd ~/llama-turboquant
HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
  cmake -B build -DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201 -DCMAKE_BUILD_TYPE=Release
HIP_PATH=/opt/rocm cmake --build build -j16 --target llama-bench llama-server
```

Clean build, 1.2 GB. The same two traps from README.md apply (`HIPCXX` must be
`clang` not `clang++`; stale `CMakeCache.txt` survives a pull).

**`-DGGML_CUDA_FA_ALL_QUANTS=ON` is not needed** — and it is worth knowing why,
because issue #12's repro uses it and it costs a much longer build. The fork
ships pre-generated flash-attention instances for the turbo types, including
`fattn-mma-turbo-instance-dkq256-*`. `dkq256` is head dim 256, which is exactly
Qwen3.8's geometry, so the default build already covers this box's hardest case.

### It runs on consumer RDNA4

Issue [#12](https://github.com/TheTom/llama-cpp-turboquant/issues/12) is
*"HIP Memory Aperture Violation with TurboQuant-3 KV-Cache Compression on AMD
Radeon RX 9070 XT (RDNA4)"* — this exact card. It was fixed by PR #176 (the f16
dequant temp buffers were using raw `cudaMalloc` during HIP graph capture), and
a contributor asked on the thread for *"a second hardware confirmation on
consumer RDNA4."*

**Confirmed here: no crash, at any context or turbo type tested, including
262,144.** The only prior confirmation was a Radeon AI PRO R9700 (same gfx1201
family, not consumer).

---

## Results

### Kernel sanity — Qwen3.5-9B-Uncensored-Q8_0, shallow

`-ngl 99 -fa 1 -ctk q8_0`, varying V only, `pp512` / `tg128`:

| `-ctv` | Prompt | Generation |
|---|---|---|
| `q8_0` | 4519.8 ± 95.9 | 57.21 ± 0.28 |
| `turbo3` | 4481.3 ± 91.1 | 57.13 ± 0.06 |
| `turbo4` | 4462.8 ± 87.2 | 57.21 ± 0.04 |
| `turbo2` | 4451.4 ± 100.9 | 57.22 ± 0.03 |

All within ~1.5% — a wash, as it should be. At 512 tokens the KV cache is
negligible, so this run proves the kernels execute correctly and costs nothing;
it says nothing about the format. The project's "91-97% of q8_0 speed" claim is
if anything pessimistic here (~99%).

### The real test — Qwen3.8-27B-UD-Q3_K_XL-v3 at depth

`-ngl 99 -fa 1 -ub 512 -p 2048 -n 64 -d 32768 -r 2`, symmetric K and V,
`TURBO_AUTO_ASYMMETRIC=0`. All four rows are the **same fork binary**, so the
deltas are clean even though the absolute numbers are not comparable to
README.md's `b10463` figures:

| KV type | Prompt @d32k | Generation @d32k |
|---|---|---|
| `q4_0` (the current 128k preset) | **530.0** ± 0.2 | 19.66 ± 0.29 |
| `turbo3` | 524.5 ± 0.1 | **23.73** ± 0.16 (+20.7%) |
| `turbo2` | 524.7 ± 0.4 | **26.02** ± 0.17 (+32.3%) |

Prompt is flat within 1% — noise. Generation gains 21-32% **over `q4_0`**, and
that qualifier is doing all the work. See the correction below before quoting
these numbers.

#### Correction: the "+21% generation" claim was baseline shopping

The table above compares turbo against **`q4_0`**. Gemma 4 was later benched
against **`q8_0`** and showed the opposite sign:

| Gemma 4-26B-A4B, `-ncmoe 8`, `-d 32768` | Prompt | Generation |
|---|---|---|
| `q8_0` | 1131.6 ± 6.2 | **45.06** ± 0.77 |
| `turbo3` | 1140.2 ± 3.9 | 43.94 ± 0.09 (**-2.5%**) |
| `turbo2` | 1151.2 ± 7.1 | 43.74 ± 0.96 (**-2.9%**) |

Both results are real and they are not in conflict. `q4_0` is slow at head dim
256; turbo recovers that penalty on Qwen3.8 and has nothing to recover on Gemma
4, which was already on `q8_0`. The consistent statement across both models is:

> **TurboQuant runs at roughly `q8_0` speed while costing a third of `q8_0`'s
> size. It is a VRAM tool, not a speed tool.**

Quoting "+21% generation" without naming the `q4_0` baseline overstates it, and
an earlier revision of this file did exactly that. The Gemma 4 numbers are the
correction that caught it — a negative result doing useful work.

### Gemma 4: the MoE payoff, and how much of it is actually TurboQuant's

For a partially-offloaded MoE the win should not come from the KV path at all —
it should come from turbo's VRAM savings letting expert layers move off DDR4 and
back onto the card. Measured, `-fa 1 -ub 512 -p 2048 -n 64 -d 32768 -r 2`:

| KV | `-ncmoe` | Prompt | Generation |
|---|---|---|---|
| `q8_0` | 8 (current preset) | 1131.6 ± 6.2 | 45.06 ± 0.77 |
| `q8_0` | **4** | 1293.0 ± 3.0 | **50.29** ± 2.45 |
| `q8_0` | 2 | **fails to create context** | — |
| `q8_0` | 0 | **fails to create context** | — |
| `turbo2` | 8 | 1151.2 ± 7.1 | 43.74 ± 0.96 |
| `turbo2` | 4 | 1298.0 ± 3.2 | 48.95 ± 1.81 |
| **`turbo2`** | **2** | **1399.2** ± 5.0 | **56.12** ± 2.32 |

**Most of the available gain is not TurboQuant's.** `-ncmoe 8 → 4` is worth
+14% prompt and +12% generation and works fine on plain `q8_0` — no fork, no
new KV format. `switch-model.sh` ships `gemma4:32k` at `-ncmoe 8`, which is
simply over-conservative at this context; that is free performance sitting in
the current setup and it should be re-tuned regardless of anything in this file.

At `-ncmoe 4` the two KV formats tie on prompt and `q8_0` is *ahead* on
generation (50.29 vs 48.95), so turbo earns nothing there.

**What turbo does buy is the next step down.** `q8_0` cannot allocate at
`-ncmoe 2`; `turbo2` can, and that step is worth a further +8% prompt and +12%
generation. Against the shipping preset the total is +23.6% / +24.5%, but only
the last third of it is attributable to TurboQuant.

This is the same lever as the Qwen3.8 quant tier, cashed out differently: on a
dense model the freed VRAM buys **better weights**, on an MoE it buys **fewer
CPU-resident experts**. In both cases the honest test is the control — run the
same configuration on a stock KV type and see whether it was reachable anyway.
Here it was, for most of the range, and an earlier draft of this file credited
turbo with the whole thing.

### Capacity — llama-server, measured VRAM

`-ngl 99 -ub 512 -b 2048 -fa on`. GTT tracked because peak VRAM alone cannot
distinguish a fit from a host spill (README.md's `-ngl 44` lesson). Idle
baseline 57 MiB; **GTT delta was +6 MiB on every row — no spill anywhere.**

| Config | VRAM | Free | GTT delta |
|---|---|---|---|
| `q4_0` @ 131,072 (current preset) | 15,673 | 631 MiB | +6 |
| `turbo3` @ 131,072 | **14,950** | **1,354 MiB** | +6 |
| `turbo3` @ 196,608 | 16,069 | 235 MiB | +6 |
| `turbo2` @ 262,144 | 16,295 | 9 MiB | +6 |

**RETRACTED — 262,144 does not work. Re-tested and it crashes.** An earlier
revision of this file reported "native 262,144 loads" as a headline result,
against README.md's record that no quant fits that context. That was measured
at load time only and never put under a real prompt.

Re-run properly at `-ub 256` (which loads with 94 MiB free rather than 9), it
**core-dumped 30,720 tokens into the prefill** — 25% of the way through a
121,836-token prompt:

```
HSA_STATUS_ERROR_OUT_OF_RESOURCES ... Available Free mem : 0 MB
llama-server: Aborted (core dumped)
```

README.md's original statement was right and this file was wrong to challenge
it on load-time evidence. The last two rows above should be read as
**"allocated", not "usable"** — and the 196,608 row (235 MiB free) sits below
the ~500 MiB working threshold too, so assume it fails the same way until
someone prefills it.

**The useful row is `turbo3` @ 131,072**: same context as the shipping preset,
+21% generation, and 1,354 MiB free against 631 — more than double the headroom,
which is exactly the margin that gets eaten when a browser or Resolve is open.

### The capacity result — real, reproducible, and NOT worth adopting

> **Superseded by the [KL-divergence measurement](#kl-divergence-the-measurement-that-reversed-the-recommendation).**
> Everything in this section is accurate: the fit is real, the control is
> sound, and the retrieval scores are genuine. It is kept because the *fit*
> findings stand on their own and the `-ub` lesson is worth having. But the
> conclusion it originally carried — adopt this config — was wrong, and KLD is
> why. Read it as "what TurboQuant can make fit", not "what to run".

Without TurboQuant this card must **drop a quant tier to reach 128k**. `IQ4_XS`
is the 32k preset; `Q3_K_XL` is what 64k and 128k run, because the smaller
trunk is what buys the context. TurboQuant removes that constraint — at a
quality price that was not measured until later.

All rows: `-ngl 99 -b 2048 -fa on -c 131072`, `TURBO_AUTO_ASYMMETRIC=0`, needle
at `--depth 114000` (~121,836 actual tokens).

| Model | KV | `-ub` | Load | Deep prefill | Needle |
|---|---|---|---|---|---|
| `Q3_K_XL-v3` (3.802 BPW) | `q4_0` | 512 | 631 MiB free | ✓ | **5/5** |
| `IQ4_XS-v3` (better) | `q4_0` | 256 | **cannot allocate** | — | — |
| `IQ4_XS-v3` | `turbo3` | 512 | 304 MiB free | ✗ **crash @17%** | — |
| `IQ4_XS-v3` | `turbo2` | 512 | 700 MiB free | ✗ **crash @30%** | — |
| **`IQ4_XS-v3`** | **`turbo2`** | **256** | **803 MiB free** | **✓** | **5/5** |

The winning row was re-run for semantic recall and scored **5/5 at 117,170
tokens**, so it passes both retrieval instruments, not just needle.

The control is the important row. `IQ4_XS` + `q4_0` + `-ub 256` fails at load
with `graph_reserve: failed to allocate compute buffers`, so `-ub 256` alone
does **not** produce this result — the KV savings are doing the work.

Prefill is not the cost it looks like: 319s for ~122k against the `Q3_K_XL`
baseline's 328s. The smaller ubatch paid for itself.

**A fit at load is not a fit.** Three configs here allocated cleanly and then
died mid-prefill with
`HSA_STATUS_ERROR_OUT_OF_RESOURCES ... Available Free mem : 0 MB`.

**`-ub` is the predictor, not free VRAM at load.** That is worth stating
carefully, because the obvious reading of the table is wrong. Free VRAM at load
tracked *how far* the prefill got within a fixed ubatch (304 MiB → 17%,
700 MiB → 30%), which invites a rule like "keep 500 MiB free." That rule is
false: the winning `-ub 256` config was later re-run when the desktop happened
to be holding more VRAM, loaded with only **267 MiB free**, peaked at 174 MiB
free, and completed a full 117,170-token prefill without trouble — while
`-ub 512` died starting from 700 MiB.

The reason is that the prefill compute buffer scales with ubatch, so `-ub 256`
roughly halves the growth that has to fit in whatever is left. **Reach for
`-ub 256` before concluding a context does not fit**; README.md already uses
this lever for the 1M Qwen3-Coder-Next config and for `glm4.7-flash`. It costs
little — 319s vs 328s for the same 122k prefill here.

This is README.md's `-ngl 44` lesson restated for context length: peak VRAM at
load says nothing about what a long prompt will demand.

**The awkward part: this rests on `turbo2`,** the most aggressive format and the
one with the least quality evidence. `turbo3` — the format validated below with
both needle *and* semantic recall — does not fit here. The tier upgrade needs
the less-proven format.

### Quality at depth — turbo3 vs q4_0, the preset-relevant A/B

Both arms: Qwen3.8-27B-UD-Q3_K_XL-v3, `-c 131072 -ngl 99 -ub 512 -b 2048 -fa on`,
same binary, same haystacks, same run. `needle-test.py` and
`semantic-recall-test.py` from `~/llama.cpp`.

| Arm | VRAM (free) | Needle @121,836 | Semantic @117,170 |
|---|---|---|---|
| `q4_0` (control) | 15,891 (413 MiB) | **5/5** | **5/5** |
| `turbo3` | **14,950 (1,354 MiB)** | **5/5** | **5/5** |

Identical retrieval, 941 MiB cheaper, +21% generation. The needle depths
(5/25/50/75/95%) both edges and the middle, which is where decay shows first.

**Read this as "no regression", not "no difference."** Both arms score 5/5 —
the test saturates, so it cannot rank two configurations that both pass. What
it rules out is the failure mode that actually matters: `turbo3` does not
degrade long-range attention at the context this box would use it at. Ranking
them would need a harder instrument — KLD against f16 KV at long context, or a
needle set with more, closer-spaced facts.

**Perplexity at `-c 512` would not have helped.** The fork's own
`docs/quality-benchmarks.md` prescribes exactly that, and for a KV-cache format
it is close to meaningless: at 512 tokens the cache barely exists, so the run
measures the weights, not the KV quantizer. Any perplexity or KLD number
offered for these types at short context should be treated as uninformative.

---

## Gotchas

**1. `TURBO_AUTO_ASYMMETRIC` defaults to 1 and silently overrides `-ctk`.**
The first 262,144 attempt failed with:

```
ggml_backend_cuda_buffer_type_alloc_buffer: allocating 5644.00 MiB on device 0:
  cudaMalloc failed: out of memory
```

5,644 MiB is 22,576 bytes/token — nowhere near 2-bit. The knob auto-selects
asymmetric K/V for large-GQA models and had quietly kept K at high precision.
`TURBO_AUTO_ASYMMETRIC=0` gives true symmetric turbo and the same context then
fits in 2,048 MiB of KV. **Anything measuring these types must set it
explicitly, or it is measuring something other than what it asked for.**

Other knobs, all left at default here: `TURBO_LAYER_ADAPTIVE` (0),
`TURBO_SPARSE_V` (1), `LLAMA_ATTN_ROT_*` (off — TurboQuant manages its own
rotation).

**2. A thinking model plus a small `max_tokens` looks exactly like corruption.**
Qwen3.8 emits `reasoning_content` first. At `max_tokens: 80` the budget was
consumed before any `content` was produced, and the harness reported empty
output for `turbo3` at two different contexts. That was very nearly written up
as decode corruption — plausible, since #241 (*"turbo3 V-cache produces
corrupted output"*) is a real closed bug. It was the harness. Raising the budget
gives `{"content":"Hello!","reasoning_content":"We need to respond..."}`.
**Parse `reasoning_content` before calling any thinking model broken.**

**3. `dflash-kquant.gguf` cannot be used as a smoke test.** It fails context
creation — but it fails identically on baseline `f16`, so it is the model (a
draft/MTP model, not standalone-runnable), not the backend.

### Running the recall tests against a thinking model

Three separate harness faults blocked the quality run above, none of them
TurboQuant's. They are recorded because they apply to **any** `needle-test.py`
or `semantic-recall-test.py` run against a Qwen3.8 preset, turbo or not.

**4. `--depth` undershoots and the request 400s.** `--depth 126000` built a
134,712-token haystack; `semantic-recall-test.py` built 148,476. Both blew past
`-c 131072` and the server correctly refused:

```
send_error: task id = 0, error: request (134712 tokens) exceeds the available
  context size (131072 tokens), try increasing it
```

Both scripts size the filler by tokenizing `FILLER.format(i=0)` once, but the
loop runs to five-digit `i` and those indices tokenize longer, so the estimate
is systematically low — ~7% for needle, ~18% for semantic. Ask for **`--depth
114000` (needle) and `--depth 100000` (semantic)** to land at ~121.8k and
~117.2k in a 131,072 context.

**5. The 60-token answer budget is consumed entirely by reasoning.** Qwen3.8
emits `reasoning_content` first, so `max_tokens: 60` returns
`finish_reason: "length"`, 60 completion tokens, and an **empty `content`**:

```json
{"content": "", "reasoning_content": "We need answer user's request. ...
   Need answer: The sessions table has 31"}
```

The score collapses without anything being wrong. **This is not subtle in
effect and very subtle in appearance** — the baseline `q4_0` config scored
**1/5 at 8,198 tokens**, a depth with essentially no KV pressure at all. Run
the shallow sanity pass first for exactly this reason: a bad score at 8k is
proof of a broken harness, because nothing about KV quantization can fail
there.

**6. `--reasoning-budget 0` does not disable thinking here** — measured, still
60 reasoning tokens and empty content. The working lever is the one
`switch-model.sh` already uses for `laguna`:

```bash
--chat-template-kwargs '{"enable_thinking":false}'
```

That restored 5/5 at 8k and is what both arms of the A/B above ran with. It is
applied server-side, so it affects both arms identically and does not bias the
comparison.

---

## What has NOT been established

Open issue #305 reports that *any* quantized K cache badly degrades
attention-sink models such as gpt-oss, and `turbo2` is the most aggressive K
quantizer available. Nothing in this file tests that class of model.

---

## KL-divergence: the measurement that reversed the recommendation

Both retrieval tests saturate — `turbo2` and `q4_0` each score 5/5, which
establishes no-regression and cannot rank. KLD does not saturate: it compares
the full 151,936-entry output distribution token by token, so it returns a
continuous number.

**Method.** Reference is the *same weights* with **f16 KV**, which isolates the
KV quantizer from everything else. `-c 32768`, `--chunks 2` (65,536 tokens of
wikitext-2), `Qwen3.8-27B-UD-Q3_K_XL-v3`, base PPL 6.1684 ± 0.0798. 32,768 is
the deepest f16 KV that fits on this card (2,048 MiB of cache + 12,537 of
weights); the base logits file is 16.3 GB at ~297 KB per token evaluated.

| KV | bits/val | Mean KLD | 99.9% KLD | Same top-p | RMS Δp | PPL | ΔPPL |
|---|---|---|---|---|---|---|---|
| `q8_0` | 8.5 | **0.000744** ± 0.000014 | 0.0178 | 98.54% | 0.78% | 6.1699 | +0.02% |
| `q4_0` | 4.5 | **0.003901** ± 0.000059 | 0.0830 | 97.03% | 1.73% | 6.1858 | +0.28% |
| `turbo3` | 3.25 | **0.009823** ± 0.000098 | 0.2116 | 95.24% | 2.68% | 6.2241 | +0.90% |
| `turbo2` | 2.0 | **0.030743** ± 0.000337 | 0.7045 | 92.34% | 4.72% | 6.3607 | +3.11% |

**`turbo3` is 2.5x worse than `q4_0`; `turbo2` is 7.9x worse.**

### Why this kills the quant-tier upgrade

README.md records `Q3_K_XL-v3`'s **weight** quantization at **0.0263 mean KLD /
92.94% top-1** against BF16. `turbo2`'s **cache alone** costs **0.0307 / 92.34%**
— more than the entire weight quantization of the model.

The tier upgrade was `IQ4_XS` + `turbo2` versus `Q3_K_XL` + `q4_0`: better
weights bought with a worse cache. The arithmetic does not work.

| Config @131,072 | Weight cost | Cache cost | Combined |
|---|---|---|---|
| `Q3_K_XL-v3` + `q4_0` (current) | 0.0263 | 0.0039 | ~0.030 |
| `IQ4_XS-v3` + `turbo2` | < 0.0263 | 0.0307 | > 0.031 |

Even granting `IQ4_XS` a *perfect* 0.0 weight cost — impossible, it is a 4-bit
quant — `turbo2`'s cache alone already exceeds the current configuration's
total. **The trade cannot be won.** Stay on `Q3_K_XL` + `q4_0`.

Two things make this conclusion stronger rather than weaker:

* **It is measured at 32k, and the preset runs at 131,072.** KV quantization
  error compounds with depth, so 128k can only be worse than these numbers.
  There is no f16 reference at 131,072 on a 16GB card, so this cannot be
  measured directly — but the direction is not in doubt.
* **PPL would have hidden it.** `turbo3` moves perplexity by +0.90%, which
  matches the TurboQuant paper's "~1% PPL loss" claim almost exactly. Over the
  same run, top-1 agreement fell 1.8 points and KLD tripled. Perplexity scores
  only the token that actually came next; it is close to blind to redistribution
  among the rest of the vocabulary, which is precisely what a rotated 3-bit
  codebook does.

### What retrieval testing missed, and why that matters

`turbo2` scored **5/5 needle at 121,836** and **5/5 semantic at 117,170** — on
the very configuration KLD now rejects. Both tests were run properly and both
results are real. They simply cannot distinguish a config at 0.0039 KLD from one
at 0.0307 when both retrieve a planted fact correctly.

The lesson generalises past TurboQuant: **needle and semantic recall are
regression alarms, not quality instruments.** They answer "is long-range
attention broken", and nothing finer. Any claim of the form "quantization X is
as good as Y" needs KLD or an equivalent distributional measure.

**KLD at 131,072.** The KLD above is measured at 32,768, because f16 KV does not
fit at 131,072 on a 16GB card and there is therefore no reference to compare
against. Since KV error compounds with depth, the real 128k penalty is larger
than the numbers reported here — but by how much is unmeasured. Closing that gap
needs a smaller model where f16 KV fits deep (Qwen3.5-9B would reach 128k+),
trading model relevance for depth. Not worth doing unless the conclusion is
being challenged, since the direction already decides the question.

**Coverage — four models, and only two carry conclusions:**

| Model | Role | Outcome |
|---|---|---|
| `Qwen3.8-27B-UD-Q3_K_XL-v3` | primary | depth perf, capacity, needle + semantic |
| `Qwen3.8-27B-UD-IQ4_XS-v3` | the quant-tier result | 5/5 needle @121,836 with `turbo2`+`ub 256` |
| `gemma-4-26B-A4B-it-UD-Q4_K_M` | second architecture (MoE) | no speed gain at fixed `-ncmoe`; enables `-ncmoe 2`, which `q8_0` cannot reach. Caught the baseline error |
| `Qwen3.5-9B-Uncensored-Q8_0` | kernel sanity | ran clean, shallow only, a wash by design |
| `dflash-kquant` | attempted | **no data** — fails on baseline `f16` too (draft/MTP model) |

Nothing here covers GPT-OSS (MXFP4, and issue #305 says attention-sink models
degrade with *any* quantized K), the MoE models, or Qwen3-Coder-Next. Head dim
256 and hybrid attention — Qwen3.8's properties, and what most of this file
rests on — are exactly what issue #294 concerns.

## Other open caveats

* **#294** — turbo K-cache flash attention spills 295-720 VGPRs at head size
  256. Filed against CDNA/RDNA2/RDNA3, not RDNA4, but head dim 256 is Qwen3.8's
  geometry, so if RDNA4 generation numbers ever look inexplicably low at
  `-ctk turbo*`, start here. Mixing `-ctk q8_0 -ctv turbo3` is the
  configuration the project's own docs recommend and sidesteps it.
* **#159** — *"Vulkan turbo_wht + turbo3 FA wiring missing on current main (lost
  in b9190 upstream sync)"*. They have already silently lost turbo wiring in a
  previous upstream merge. Any rebase of this fork onto newer llama.cpp must be
  re-verified end to end, not assumed; flash-attention kernels are both the
  highest-churn area upstream and where the turbo `dkq256` instances live.
* The fork is 165 commits behind. Merge upstream **into** it; rebasing 1,756
  commits across 300 files is not a real option.

## Reproducing

```bash
export TURBO_AUTO_ASYMMETRIC=0     # mandatory, see Gotcha 1

# depth benchmark
~/llama-turboquant/build/bin/llama-bench \
  -m ~/llama.cpp/models/Qwen3.8-27B-UD-Q3_K_XL-v3.gguf \
  -ngl 99 -fa 1 -ub 512 -ctk turbo3 -ctv turbo3 \
  -p 2048 -n 64 -d 32768 -r 2

# capacity check / quality server (note the thinking flag — see Gotcha 6)
~/llama-turboquant/build/bin/llama-server \
  -m ~/llama.cpp/models/Qwen3.8-27B-UD-Q3_K_XL-v3.gguf \
  -ngl 99 -ub 512 -b 2048 -fa on -ctk turbo3 -ctv turbo3 -c 131072 \
  --temp 1.0 --top-p 0.95 --top-k 20 --min-p 0.0 \
  --chat-template-kwargs '{"enable_thinking":false}' \
  --host 127.0.0.1 --port 8099

# recall at depth — sanity pass FIRST, a bad score at 8k means a broken harness
python3 ~/llama.cpp/needle-test.py --host http://127.0.0.1:8099 --depth 8000
python3 ~/llama.cpp/needle-test.py --host http://127.0.0.1:8099 --depth 114000
python3 ~/llama.cpp/semantic-recall-test.py --host http://127.0.0.1:8099 --depth 100000
```

VRAM from `/sys/class/drm/card1/device/mem_info_vram_used`, GTT from
`mem_info_gtt_used` in the same directory — check both, peak VRAM alone will
call a host spill a fit.
