# TurboQuant KV-Cache Quantization — CachyPC

Measured 2026-08-25 on the RX 9070 XT (gfx1201, RDNA4, 16,304 MiB) described in
[README.md](README.md). Everything here is from this box; nothing is quoted
from the project's own claims without being re-measured.

**Verdict up front: TurboQuant buys this card one quantization tier at 128k, and
that is the whole reason to care.** `Qwen3.8-27B-UD-IQ4_XS-v3` runs at 131,072
with `turbo2` and `-ub 256` — verified under a real 121,836-token prefill, 5/5
needle, 803 MiB free. The same model at 131,072 with `q4_0` **cannot even
allocate its compute buffers**. So the tier upgrade is caused by TurboQuant, not
by the ubatch change; the control was run.

Speed is a much weaker story than an earlier draft of this file claimed — see
[Correction](#correction-the-21-generation-claim-was-baseline-shopping). Treat
TurboQuant as a **VRAM tool, not a speed tool**: roughly `q8_0` quality-of-life
at a third of the size.

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

Gemma 4 has its own untested angle: it runs `-ncmoe 8`, so its win would come
from turbo's VRAM savings letting expert layers move back onto the GPU, not
from the KV path. Not measured.

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

### The result that matters: a quantization tier at 128k

Without TurboQuant this card must **drop a quant tier to reach 128k**. `IQ4_XS`
is the 32k preset; `Q3_K_XL` is what 64k and 128k run, because the smaller
trunk is what buys the context. TurboQuant removes that trade.

All rows: `-ngl 99 -b 2048 -fa on -c 131072`, `TURBO_AUTO_ASYMMETRIC=0`, needle
at `--depth 114000` (~121,836 actual tokens).

| Model | KV | `-ub` | Load | Deep prefill | Needle |
|---|---|---|---|---|---|
| `Q3_K_XL-v3` (3.802 BPW) | `q4_0` | 512 | 631 MiB free | ✓ | **5/5** |
| `IQ4_XS-v3` (better) | `q4_0` | 256 | **cannot allocate** | — | — |
| `IQ4_XS-v3` | `turbo3` | 512 | 304 MiB free | ✗ **crash @17%** | — |
| `IQ4_XS-v3` | `turbo2` | 512 | 700 MiB free | ✗ **crash @30%** | — |
| **`IQ4_XS-v3`** | **`turbo2`** | **256** | **803 MiB free** | **✓** | **5/5** |

The control is the important row. `IQ4_XS` + `q4_0` + `-ub 256` fails at load
with `graph_reserve: failed to allocate compute buffers`, so `-ub 256` alone
does **not** produce this result — the KV savings are doing the work.

Prefill is not the cost it looks like: 319s for ~122k against the `Q3_K_XL`
baseline's 328s. The smaller ubatch paid for itself.

**A fit at load is not a fit.** Three configs here allocated cleanly and then
died mid-prefill with
`HSA_STATUS_ERROR_OUT_OF_RESOURCES ... Available Free mem : 0 MB`. Free VRAM at
load predicted *how far* the prefill got (304 MiB → 17%, 700 MiB → 30%) but not
whether it finished. The working config peaked at 15,940 MiB — **439 MiB of
compute-buffer growth after load.** Anything with less than roughly 500 MiB free
at load should be assumed to die under a long prompt until proven otherwise.
This is README.md's `-ngl 44` lesson, restated for context length.

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

**`turbo2` quality — one data point, and it is load-bearing.** `turbo2` has
passed 5/5 needle at 121,836 tokens on `IQ4_XS`, which is the only reason the
quant-tier result stands. But it has had **no semantic-recall run and no KLD**,
where `turbo3` got both. That is backwards: the format the recommendation
depends on is the less-validated one. Open issue #305 also reports that *any*
quantized K cache badly degrades attention-sink models such as gpt-oss, and
`turbo2` is the most aggressive K quantizer here. **Run semantic recall on the
`IQ4_XS` + `turbo2` + `-ub 256` config before treating it as a preset.**

**Ranking `turbo3` against `q4_0`.** The recall tests saturate at 5/5 for both,
so they establish no-regression and stop there. Separating them needs KLD
against an f16-KV base **at long context** — `llama-perplexity` is now built in
the fork tree, and `kld/wikitext-2-raw/` is already on disk. Note the base
logits file for a long-context run is large; that is the reason it was not done
in the same sitting.

**Coverage — four models, and only two carry conclusions:**

| Model | Role | Outcome |
|---|---|---|
| `Qwen3.8-27B-UD-Q3_K_XL-v3` | primary | depth perf, capacity, needle + semantic |
| `Qwen3.8-27B-UD-IQ4_XS-v3` | the quant-tier result | 5/5 needle @121,836 with `turbo2`+`ub 256` |
| `gemma-4-26B-A4B-it-UD-Q4_K_M` | second architecture | no speed gain vs `q8_0`; caught the baseline error |
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
