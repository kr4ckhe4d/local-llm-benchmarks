# llama.cpp `5e03bdd87` (b11434): 89 commits, measured before switching

Measured 2026-10-06, before moving the router from build 11345 (`a868c3e3c`,
2026-10-01) to b11434 (`5e03bdd87`, 2026-10-05). Two cards (R9700 + RX 9070
XT, see [r9700+rx9070.md](r9700+rx9070.md)), ROCm 7.2.4, same flags
(`-DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201`, Release). Raw output, scripts and
every server log are in
[`benchmarks/raw/llama-b11434/`](benchmarks/raw/llama-b11434/).

**The short version.** A wash with two winners and two small losers. Laguna
gains 4% and GLM 5%. gpt-oss-20b loses 3.6%, and Qwen3.8's 128K-depth prefill
loses 4%. Everything else, MTP acceptance included, did not move. The router
was switched anyway: the gains are on two of the more-used MoE models, and the
build carries upstream fixes to speculative decoding and to the multi-GPU
memory reserve. 11345 stays built at `~/llama.cpp-b11345` as a fallback.

## Why measure at two temperatures

The relevant upstream changes were all to speculative decoding at
temperature > 0:

* `spec : add probabilistic sampling for simple draft and MTP` (#27694)
* `spec : fix n-gram drafts rejected at temp > 0 after truncation` (#29924)
* `graph: gather the recurrent states once so the reserve covers every split` (#29856)

Every earlier figure in this repo uses the probe at temperature 0. The presets
themselves sample at 1.0, which is where #27694 could show. So each build was
probed at both: eight presets, the 700-token code probe, three runs each,
`seed 42`, both builds back to back with the router down. The script is
`preset_probe.py` with `BIN` pointing at either build.

## Generation, tok/s, median of 3

| Preset | 11345, t=0 | **b11434, t=0** | 11345, t=1 | **b11434, t=1** | Change |
|---|---|---|---|---|---|
| qwen3.8-27B-32k (IQ4_XS + MTP) | 71.39 | 71.33 | 70.27 | 70.37 | — |
| qwen3.8-27B-q8-128k (+ MTP) | 50.51 | 50.43 | 50.04 | 49.96 | — |
| gemma4-26B-A4B-32k (+ MTP) | 143.40 | 143.26 | 138.70 | 138.30 | — |
| qwen3.6-35B-A3B-128k | 73.60 | 73.33 | 73.65 | 72.98 | −0.4/−0.9% |
| laguna-33B-A3B-32k | 89.58 | **92.94** | 89.77 | **92.93** | **+3.5-3.8%** |
| glm-4.7-flash-30B-A3B-32k | 74.35 | **78.34** | 74.65 | **78.32** | **+4.9-5.4%** |
| muse-glimmer-30B-32k (+ DFlash) | 64.05 | 63.83 | 64.91 | 64.79 | — |
| gpt-oss-20b-A3.6B-32k (R9700 only) | 147.18 | **141.91** | 147.23 | **141.93** | **−3.6%** |

* **MTP did not move**, at either temperature. Qwen3.8 and Gemma, the two MTP
  families, are within 0.3% on both builds. Whatever #27694 changes in how
  drafts are accepted, it is not visible in throughput on this probe.
* **The changes are build-wide, not temperature effects.** Each preset that
  moved moved by the same amount at t=0 and t=1.
* **Laguna and GLM gain prefill too**: Laguna 151 → 159 tok/s, GLM 62 → 69,
  both warm, both temperatures.
* **gpt-oss-20b's loss is consistent**: 141.9 in all six runs on b11434
  against 147.2 in all six on 11345. Prefill also dips (244 → 239).
* Headroom on the 9070 XT is within ~100-180 MiB of 11345 on every preset,
  mostly lower. Nothing came near the 1 GiB margin.

## Qwen3.8 at 128K depth

`depth.sh`: one 128,025-token wikitext prompt, then a 256-token answer. The
11345 row is the same script on the same box the night before
(`../r9700-two-cards/logs/qwen38-rerun.txt`).

| Config | 11345 prefill | **b11434 prefill** | 11345 tg | **b11434 tg** | Draft |
|---|---|---|---|---|---|
| IQ4_XS + MTP, `-ub 512` (the preset) | 1,053 | **1,010** (−4.1%) | 27.30 | 27.34 | 59.7% both |
| IQ4_XS + MTP, `-ub 1024` | 921 | **887** (−3.7%) | 27.81 | 27.89 | 61.5% both |
| old preset, Q3_K_XL + q4_0 | 1,189 | **1,142** (−3.9%) | 9.21 | 9.23 | — |

Prefill at depth is ~4% slower on every config; generation and draft
acceptance are identical. A full 128K turn takes ~5 s longer to read (2:07
against 2:02). `-ub 512` still beats 1024, so the presets keep it.

## What switching cost

* gpt-oss-20b: 147 → 142 tok/s.
* Qwen3.8 long-context prefill: −4%.
* In exchange: Laguna +4%, GLM +5%, and upstream's speculative-decoding and
  multi-GPU reserve fixes.

## Open

* **The gpt-oss and prefill regressions are not bisected.** 89 commits; most
  are Vulkan, Metal, CUDA, SYCL or Hexagon, and none names HIP/ROCm. A bisect
  on `gpt-oss-20b` at 32k is the cheaper of the two (one 700-token probe per
  step, ~7 steps).
* **Gemma 4 `llama-perplexity`** still gives an unusable reference
  (r9700+rx9070.md, "Open"); nothing in this range mentions it, and it was not
  retested.

## Reproducing

```bash
# side build, same flags as the production one
git -C ~/llama.cpp worktree add ~/llama.cpp-b11434 5e03bdd87
cd ~/llama.cpp-b11434
cmake -B build -DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201 -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_HIP_COMPILER=/opt/rocm/lib/llvm/bin/clang
cmake --build build -j 16 --target llama-server llama-perplexity llama-bench
# router down, then:
benchmarks/raw/llama-b11434/run-ab.sh
```

`run-ab.sh` was interrupted by a power cut at 09:04 with the old build's t=0
pass done and one new-build preset in; `run-ab-resume.sh` ran the rest into
the same files. The new-build t=0 Qwen3.8 32k row comes from before the cut,
and everything after it from after the reboot.
