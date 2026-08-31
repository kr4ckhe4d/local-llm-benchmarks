# DFlash2 and the QAT Q2_0 quant — Qwen3.8-27B on 16 GB

Measured 2026-08-31 on the machine in `README.md` (RX 9070 XT, 16,304 MiB,
ROCm). Prompted by [a LocalLLaMA thread][thread] recommending
`qwen3.8-27B-qat-q2_0` + the DFlash2 drafter + `q5_0` KV at 100K context.

[thread]: https://www.reddit.com/r/LocalLLaMA/comments/1w0bnv2/

Two separate things arrived together and the thread conflates them:

* **DFlash2**, a block-diffusion drafter for speculative decoding. It works,
  and it is worth having.
* **`sdkyuan/qwen38-27b-qat-q2_0`**, a 2-bit quantisation-aware-trained
  checkpoint. It is fast because it is small, and it costs real fidelity.

---

## The build: `build/` cannot be reproduced today

**This is the finding with the longest shelf life and it has nothing to do with
DFlash2.** Any `cmake -B build -DGGML_HIP=ON` on this box now produces a broken
HIP configure. Verified by configuring the *b10463 tree itself* fresh — it fails
identically, so this is environment drift, not a llama.cpp change:

```
ld.lld: error: unable to find library -lamdhip64
```

CMake's HIP compiler-ID probe fails to link, because `/opt/rocm/lib` is known to
`ldconfig` but is not on the link-time search path. `CMAKE_HIP_COMPILER_ID` then
comes back empty, so `Compiler/Clang-HIP.cmake` never loads, so
`_CMAKE_COMPILE_AS_HIP_FLAG` is never set. The compile line loses `-x hip` and
the Release flags, ROCm's clang parses `.cu` as CUDA, and rejects `gfx1201`:

```
old:  clang $(HIP_FLAGS) -o arange.cu.o -x hip -c arange.cu   # -O3 -DNDEBUG -std=gnu++17 --offload-arch=gfx1201
new:  clang $(HIP_FLAGS) -o arange.cu.o       -c arange.cu    # --offload-arch=gfx1201 only
```

The invocation that works, and reproduces b10463's flags exactly:

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release -DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201 \
      -DCMAKE_HIP_COMPILER_ROCM_ROOT=/opt/rocm -DCMAKE_HIP_FLAGS="--rocm-path=/opt/rocm"
```

DFlash2 landed upstream on **2026-08-27** (`b10f9ca58`, PR #27342 via #27816),
ten days after `build/`'s b10463, plus a fix `cc231cb0d` on 08-30. Production
`build/` carries DFlash **v1** only — the Muse Glimmer path. Confirmed by GGUF
key, not by guess: the drafter file needs `dflash.conv_group_size`,
`dflash.selector_rank` and `dflash.selector_top_k`, and b10463 knows none of
them.

Everything below ran on a **separate worktree** at `~/llama.cpp-dflash2`
(commit `9723942ad`, build 10711), the same pattern the README describes for
`build-vulkan/`. Production `build/` was never touched.

---

## `-np 1` is mandatory, and it also moves the MTP ceiling

The DFlash2 drafter carries a **recurrent-state cache that scales with server
slot count** — about 630 MiB per slot. llama.cpp auto-selects 4. That is the
whole explanation for:

```
alloc_tensor_range: failed to allocate ROCm0 buffer of size 2510290944   # 2,394 MiB = 4 x ~600
```

The target's own KV does not scale this way (`kv_unified = true`), which is why
no existing preset needed `-np`. Every row below pins `-np 1`.

**Correction to the README.** It records MTP as failing above 32K on Qwen3.8.
That was measured at default `-np`. At `-np 1`, `-ub 256`, q4_0, MTP reaches
**64K at 69.02 tok/s, peak 15,064 MiB**. The 32K ceiling was a slot-count
artifact, not an MTP limit. Re-verified on production `build/` (b10463):
`peak=15416 free=888`, no GTT spill.

**128K is still out of reach for every drafter on this target.** Measured at
`-np 1` on b10463, MTP fails on the KV cache at both `-ub 512` and `-ub 256`.
DFlash2 fails too — the target leaves ~600-940 MiB and the drafter wants
~1,710. The 128K preset itself re-measures at `peak=15705 free=599` (the README
records 281, at four slots). So speculative decoding at 128K needs a *smaller
target* than `UD-Q3_K_XL-v3`, not different flags.

---

## DFlash2 against the in-file MTP head — `UD-Q3_K_XL-v3` target

700-token code prompt, temp 0.0, n=3, `-np 1`, build 10711.

| Context | Config | Generation | vs baseline | Peak |
|---|---|---|---|---|
| 32K | no drafter | 29.52 | — | 13,286 |
| 32K | MTP | 69.32 | 2.35x | 14,336 |
| 32K | DFlash2 `n_max=3` | 70.06 | 2.37x | 14,967 |
| 32K | **DFlash2 `n_max=5`** | **79.27** | **2.68x** | 15,266 |
| 64K | no drafter | 29.45 | — | 13,920 |
| 64K | MTP | 69.02 | 2.34x | 15,064 |
| 64K | DFlash2 `n_max=3` | 70.00 | 2.38x | 15,331 |

The 29.52 control reproduces the README's existing 29.52 for this config, so
build 10711 is not a confound anywhere in this table.

**`--spec-draft-n-max` is the whole story.** At the default 3, DFlash2 only
ties MTP. At 5 it beats it by 14% for 299 MiB. Note the drafter costs a roughly
fixed **~1,710 MiB** at `-ub 512` (16K: 13,079 → 14,788; 32K: 13,258 → 14,968),
against MTP's ~2,212–2,450 MiB.

---

## The QAT Q2_0 target changes the fit picture completely

`qwen38-27b-qat-q2_0.gguf` is 8.76 GB against `UD-Q3_K_XL-v3`'s 12.5 GB. With
the DFlash2 drafter attached, `-np 1`, q5_0 KV:

| Context | Peak | Free |
|---|---|---|
| 100K | 12,306 | 3,998 |
| 128K | 12,969 | 3,335 |
| **200K** | **14,452** | **1,852** |

The thread's "change it to 200000 if you have 16GB+" is correct. For
comparison, the README's Qwen3.8 ceiling is 128K at 281 MiB free, and 192K only
by dropping to `UD-IQ3_XXS`.

### `q5_0` KV is a trap — use `q8_0`

Without `GGML_CUDA_FA_ALL_QUANTS`, llama.cpp compiles flash-attention vec
kernels for **four** KV combinations only: `f16-f16`, `q4_0-q4_0`, `q8_0-q8_0`,
`bf16-bf16`. `GGML_CUDA_FA_ALL_QUANTS:BOOL=OFF` in both builds here. That every
preset in `README.md` already uses q8_0 or q4_0 is not a coincidence — it is the
supported set.

@128K, DFlash2 `n_max=5`, only the KV type varied:

| KV type | with drafter | no drafter |
|---|---|---|
| `q5_0` (the thread's) | 59.28 | 36.17 |
| `q4_0` | 76.24 | — |
| **`q8_0`** | **78.90** | 42.93 |

`q5_0` costs 25% with the drafter and 16% without. `q8_0` is faster *and* higher
fidelity. DFlash2 is worth **1.84x** on this target (78.90 vs 42.93).

Note the QAT baseline is itself far faster than Q3_K_XL's — 42.93 vs 29.52 —
purely because it is 8.76 GB on a bandwidth-bound card. The thread reads all of
its speed as speculative decoding; most of it is not.

---

## Fidelity: KL divergence against BF16

`kld-test.sh`, wikitext, `-c 512`, `--chunks 200`, against the same
`qwen3.8-27B-bf16.kld` base as every existing row. Both BF16 files re-downloaded
and **sha256-verified against the hashes recorded in the script** — Unsloth
re-quantises in place, so a mismatched reference would have silently invalidated
the comparison.

| Quant | Size | Median KLD | Mean KLD | Top-1 | RMS Δp |
|---|---|---|---|---|---|
| UD-Q6_K-v3 | — | 0.000777 | 0.002019 | 97.96% | 1.25% |
| UD-IQ4_XS-v3 | 14.25 GB | 0.007395 | 0.017888 | 94.08% | 3.80% |
| UD-Q3_K_XL-v3 | 13.15 GB | 0.010785 | 0.026272 | 92.94% | 4.61% |
| UD-IQ3_XXS-v3 | — | 0.025942 | 0.058933 | 89.28% | 6.88% |
| **UD-Q2_K_XL** | 9.15 GB | 0.038760 | 0.088912 | 87.02% | 8.40% |
| **QAT-Q2_0** | 8.76 GB | 0.137722 | 0.302641 | 77.67% | 16.09% |

**This reproduces the model card's own table almost exactly.** The card reports
wikitext top-1 of 78.3% (QAT) against 87.5% (UD-Q2_K_XL), and KL of 0.302
against 0.098. Measured here: 77.67% / 87.02%, and mean KLD 0.3026 / 0.0889 —
the QAT figure agrees to three decimals. **The card is accurate.** What is wrong
is the thread's reading of it as "very little degradation from q8".

Two caveats that matter:

* The card compares against a **9.83 GB** `UD-Q2_K_XL`. The current file is
  **9.15 GB** — Unsloth re-quantised in place, the exact hazard the README
  documents. The row above is "as of 2026-08-31", not a rebuttal of their table.
* Wikitext is precisely the axis the card says it traded away. This measures the
  documented cost, not a hidden one.

---

## Functional probes, and one that does not work

`run-suite.sh` at 128K, q8_0 KV, DFlash2 `n_max=5`, `-np 1`, identical flags for
both 2-bit models.

| Probe | QAT-Q2_0 | UD-Q2_K_XL | UD-Q3_K_XL-v3 |
|---|---|---|---|
| cdn-freshness | **18/54 (33%)** | 26/39 (67%) | 33/36 (92%) |
| tool calling | pass | pass | pass |
| generation @128K | 78.9 tok/s | ~70 tok/s | — |
| code-quality | 29/50 (58%) | 39/50 (78%) | 35/50 (70%) |

**Ignore that last row.** Ordered by KLD, `code-quality` reads 60% (IQ4_XS), 70%
(Q3_K_XL), 76% (IQ3_XXS), 78% (Q2_K_XL) — it *rises* as fidelity falls, and
scores the second-best quant in the file dead last. It does not order quants,
exactly as `kld-test.sh`'s header says. No conclusion about code quality can be
drawn from it in either direction, including about the card's "code is
preserved" claim, which therefore remains **untested here**.

`cdn-freshness` does discriminate — 91/92/92% across the 3- and 4-bit tiers,
then 67%, then 33%. QAT-Q2_0 invented whole `@mui/material` module paths. That
agrees with the KLD ordering and with the card's own account of what it gave up.

---

## The "empty response" reports are a `max_tokens` artifact

Several people in the thread report the model stopping without emitting a token,
and the top-voted fix is `temp 0.7`. Neither diagnosis survives measurement.
Three prompts, n=5, at each temperature:

| `max_tokens` | temp | fox-100 | lru | venv |
|---|---|---|---|---|
| 12288 | 0.7 | 5/5 | 5/5 | 5/5 |
| 12288 | 1.0 | 5/5 | 5/5 | 5/5 |
| 700 | 0.7 | 4/5 | **1/5** | 5/5 |
| 700 | 1.0 | 5/5 | **1/5** | 5/5 |

**30/30 clean at 12288, at both temperatures.** Empties appear only at 700, and
appear equally at 0.7 and 1.0. It is a thinking model; reasoning consumes the
budget before any content is emitted — the same failure this repo already
documents. Temperature showed no reliability effect.

Scope: 3 short prompts, non-agentic. The thread's *looping* reports come from
long agent sessions, which this does not reproduce. The empty-output claim is
explained; the looping claim is not addressed.

---

## Verdict

* **DFlash2: adopt.** 2.68x at `n_max=5` on Q3_K_XL, 1.84x on the QAT target,
  and it needs `-np 1` and `n_max 5` to be worth anything. Requires a build
  newer than 2026-08-27.
* **`q5_0` KV: do not use** on a stock build. `q8_0` is faster and better.
* **QAT-Q2_0: not for this box's daily driver.** It buys 200K context and ~13%
  generation over `UD-Q2_K_XL` at 0.4 GB less, and pays 3.6x median KLD and 9.4
  points of top-1 agreement for it. If a 2-bit target is wanted, `UD-Q2_K_XL` is
  the better-measured one.
* **Nothing here dislodges `UD-Q3_K_XL-v3`** as the default at 0.0108 / 92.94%.

## Harness changes made for this work

* `fit.sh`, `run-suite.sh`: `BIN` is now overridable, so a side build can be
  measured without disturbing `build/`. `run-suite.sh` already records
  `$BIN --version` in every output header, so results self-identify.
* `fit.sh`: now passes `-np 1` by default, overridable with `NP=`.
  `models-preset.ini` sets `parallel = 1` in its `[*]` section, so every router
  preset runs one slot — but `fit.sh` did not, so llama.cpp auto-selected four
  and every row it produced measured a configuration nothing serves. Worth
  ~450 MiB at 32K, and far more with a drafter attached. This mismatch is why
  the README concluded MTP caps at 32K.
* `fit.sh`: added a VRAM settle-wait before `BASE` is sampled. A killed
  llama-server does not release VRAM instantly, and back-to-back runs were
  sampling `BASE` at 12,093 MiB while the previous model was still resident.
  This produced **four false "failed to allocate buffer for rs cache" failures**
  in the first DFlash2 sweep; the same configs load fine on a quiesced card.
