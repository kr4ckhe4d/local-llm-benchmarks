# Inkling-2-Mini on the R9700: 31 to 54 tok/s in llama.cpp

Measured 2026-11-21 on the Radeon AI PRO R9700 (gfx1201, RDNA4, 32 GB, ROCm 7.2.4) described in
[r9700+rx9070.md](r9700+rx9070.md), with Unsloth's `Inkling-2-Mini-UD-Q8_K_XL` (Mainline_Support layout,
21.29 GiB, sha256 in [benchmarks/inkling-2-mini-UD-Q8_K_XL/sha256.txt](benchmarks/inkling-2-mini-UD-Q8_K_XL/sha256.txt)).

**Generation went from 31.0 to 54.0 tok/s (+74%) on the same file and card, with output that matches the
starting build within the rounding noise of the model itself.** Prompt processing moved from 825 to 876 tok/s.
The work is 16 commits on a local llama.cpp branch: Inkling's graph builder emits fewer, better ordered ops,
and the CUDA/HIP backend gains fusions that run each small piece of an Inkling layer as one kernel. One of them
is not Inkling-specific at all: on RDNA4 a matrix-vector product whose row count is a multiple of 256 runs about
twice as slow, and two idle blocks fix it.

| | starting build | `inkling2-speedups` | |
|---|---:|---:|---:|
| tg128 (ROCm) | 31.0 | **54.0** | +74% |
| tg64 @ 4K depth | 39.8 \* | 52.0 | |
| tg64 @ 16K depth | 38.1 \* | 49.8 | |
| pp512 | 825 | 876 | +6% |
| pp4096 | 627 | 653 | +4% |
| tg128 (Vulkan, RADV) | 27.0 | 30.3 | +12% |

\* the depth rows of the starting column were measured midway, after the fourth commit (40.2 tok/s at depth 0),
not on the starting build; the starting build's depth numbers were not taken.

Raw data: [throughput-final.txt](benchmarks/inkling-2-mini-UD-Q8_K_XL/speedups/throughput-final.txt),
[build-equivalence-kld.txt](benchmarks/inkling-2-mini-UD-Q8_K_XL/speedups/build-equivalence-kld.txt),
[tests-final.txt](benchmarks/inkling-2-mini-UD-Q8_K_XL/speedups/tests-final.txt), and the 16 commits as
patches in [speedups/patches/](benchmarks/inkling-2-mini-UD-Q8_K_XL/speedups/patches/).

## Why it was slow

Inkling-2-Mini is Thinking Machines' 26B looped MoE: 24 stored layers, with layers 6 to 18 run three times, so
48 layer passes per token over about 5 GB of weights. At 640 GB/s that allows roughly 120 tok/s; it ran at 31.

It is not ROCm: the same file on the same card through Vulkan was slower (27.0). The time goes into the number
of operations. llama.cpp's own graph export ([graph-ops.txt](benchmarks/inkling-2-mini-UD-Q8_K_XL/graph-ops.txt))
counted 12,178 nodes per generated token, about 8,000 of them real kernels: every pass adds short convolutions,
relative-position attention, attention over earlier block outputs ("block attention residuals"), loop
controllers and SITU activations, mostly on vectors of 2,304 values or less. `test-backend-ops perf` on the
R9700 ([op-perf-rocm.txt](benchmarks/inkling-2-mini-UD-Q8_K_XL/op-perf-rocm.txt)) put each of those small ops at
2.2 to 3.4 us, while the weight matmuls ran at 540 to 660 GB/s. Summed, weight reads were about 8 ms of a 32 ms
token, the other 24 ms small kernels. HIP graphs were in use and changing their chunk size made no difference,
nor did the HIP runtime's launch knobs: the cost is inside the GPU, per kernel.

So the work was: fewer kernels per token, and no slow ones among those left.

## What changed

Each step was measured with `llama-bench -fa 1 -lm dio -r 3` on the R9700. Kernel counts are the kernels the
backend actually launched for one generated token, after fusion, logged with a temporary counter.

| step | tg128 | kernels / token |
|---|---:|---:|
| start: PR #32704 on #32694 (2a28df0f9) | 31.0 | (~8,000 unfused ops) |
| graph: clip as `threshold * l2_norm(x, threshold)` (3 ops, not 9), block stack built once per prefix, no-op `cont`s dropped, controller norms shared | 34.9 | |
| graph: F16 mask cast to F32 once per graph, not per layer | 35.1 | |
| backend: top-k MoE router fusion accepts the `sum + eps` normalization Inkling (and DeepSeek-V4.1) use instead of a clamp | 35.6 | |
| backend: fused softcap reads strided rows (SITU's gate and up are halves of the fused gate_up) | 36.1 | |
| backend: `SSM_CONV -> ADD(residual) -> SCALE` as one kernel | 37.3 | |
| **backend: pad the mmvf grid on RDNA4 when the row count is a multiple of 256** | 39.1 | |
| graph: Q/K clip threshold folded into the attention scale; one-token bias table from a swapped product | 40.2 | |
| backend: `TANH + MUL` fusion, like the existing SILU/SIGMOID/SOFTPLUS ones | 40.5 | 4,389 |
| controller `mul(message, gain)` operand order, so its tanh and mul are adjacent | 40.9 | 4,293 |
| backend: up to four consecutive matvecs on the same vector in one launch; graph: same-input projections side by side | 42.3 | 4,023 |
| backend + graph: one-token conv step (history concat, state store, convolution, residual, scale) as one kernel | 44.0 | 3,681 |
| backend: alloc dep so the NVFP4 down projection's per-expert scale always fuses | 44.1 | 3,653 |
| backend: one-token attention over stored block outputs (6 ops per mix, 115 mixes) as one kernel | 46.3 | 3,078 |
| backend + graph: loop controller (two small matvecs, two tanh gates, combine) as one kernel | 48.6 | 2,699 |
| graph: dynamic conv taps folded into the conv weights for one token (17 kernels to 3) | 50.0 | 2,481 |
| backend: `MUL -> L2_NORM -> SCALE` for few rows (clipped Q and R) | 51.0 | 2,337 |
| backend: relative-position bias computed only for the gathered entries, straight to F16 | **54.0** | **2,138** |

The prompt-processing path (512-token ubatches) keeps the separate kernels for everything batch-shaped; the
fusions only match one token, and `MUL -> L2_NORM` is limited to 1,024 rows because the fused kernel was slower
on a 512-token batch.

### The RDNA4 matvec grid

`test-backend-ops perf` timings of a 2304-column BF16 matrix-vector product looked erratic: 1,152 rows in 8.4 us
but 1,024 rows in 17.2 us. Across sizes, every row count that was a multiple of 256 ran about twice as slow
(256, 512, 768, 1,024, 1,280, 1,536, 2,048, 2,304, 2,560), and inside the model a timing-only hack that gave the
K and V projections 1,088 rows instead of 1,024 made generation faster, not slower (37.6 to 38.8 tok/s).
`mul_mat_vec_f` launches one block per row; adding one or more idle blocks that return immediately removed the
penalty (1,024 rows 17.2 to 7.9 us, 512 rows 14.5 to 4.9 us, 2,304 rows 23.9 to 14.7 us). The quantized
`mul_mat_vec_q` and the `MUL_MAT_ID` launches showed no such effect. The patch pads by two blocks on RDNA4 only,
the one generation measured. It should matter to any BF16/F16/F32 model on these cards. On the router's Gemma 4
12B BF16 it gives +1.9% generation (23.19 to 23.64 tok/s, llama-bench tg128 without MTP), with identical output
([below](#rebased-onto-upstream-and-in-the-router-2026-11-22)).

## Is the output the same?

There is no bit-exact reference: fusions change the order of float sums, and Inkling routes every token to 8 of
128 experts per layer, so a rounding difference occasionally picks a different expert. The yardstick is the
starting build against itself: run with one token per batch (`-ub 1`, the generation path) and with 512-token
batches over the same text, it differs by **KLD 0.00168, 98.0% same top token** (measured during the session,
not saved to a file). The final branch against the starting build's logits
([build-equivalence-kld.txt](benchmarks/inkling-2-mini-UD-Q8_K_XL/speedups/build-equivalence-kld.txt)):

| | mean KLD | same top token | PPL (base) |
|---|---:|---:|---|
| batch 1, 4 chunks (generation path) | 0.0018 | 98.2% | 6.543 (6.559) |
| batch 512, 16 chunks | 0.0021 | 97.7% | 8.204 (8.181) |
| Vulkan, batch 1 | 0.0016 | 98.4% | |

Each new fusion has a `test-backend-ops` case that runs the same graph on the CPU backend and compares; all pass
on ROCm ([tests-final.txt](benchmarks/inkling-2-mini-UD-Q8_K_XL/speedups/tests-final.txt)), as do the existing
`TOPK_MOE`, `SSM_CONV`, `SOFTCAP`, `MUL_MAT_ID` and `MUL_MAT` suites. The one `MUL_MAT` failure (F16, n =
2,105,344) fails the same way without these commits. A chat request at reasoning effort 0.9 ran at 50 tok/s and
returned a `merge_intervals` that passed its own asserts.

## Two bugs found on the way

- **NaN after the first chunk.** The fused kernels run at the first node of their pattern but write the output
  of the last, and the allocator may place that output in the memory of an input that dies inside the pattern.
  The relative-bias fusion read `Rcur` while its output had been placed over it, and a batch-1 perplexity run
  went NaN from its second chunk on. Every custom fusion now refuses to fuse when an output overlaps an input
  read across threads, and `graph_optimize` adds alloc deps for these patterns so that the refusal is rare
  (all of them fuse in the final build).
- **CPU abort.** An intermediate version fed a permuted view into an `ADD`, which ROCm and Vulkan accept and the
  CPU backend rejects (`binary-ops.cpp: GGML_ASSERT(nb00 == sizeof(src0_t))`). The `cont` is back. The full model
  was not run on CPU alone; the test case covering that graph was.

## What did not help

- HIP runtime knobs (`HIP_FORCE_DEV_KERNARG`, `GPU_MAX_HW_QUEUES`, graph segment scheduling): no change.
- HIP graph chunk sizes from 128 to whole-graph: no change, launch is not the bottleneck.
- The grid padding on the quantized and expert matvecs: no effect.
- A first single-block depth-mix kernel with one reduction per state and query: barely faster than the six
  kernels it replaced (+0.5 tok/s). Rewritten as one pass for all dot products and the norm, it gave +2.3.

## Rebased onto upstream, and in the router (2026-11-22)

PR #32704 landed upstream as `690b87d88`. The branch was rebased onto upstream `b05204927` without conflicts
(`git range-diff`: all 16 commits unchanged) and is `5d307fdc7` in the fork. Before the router's build took it,
the rebased branch was compared with plain upstream `b05204927` on the router's other models: KLD against the
upstream build's logits at batch 512 (16 chunks) and batch 1 (4 chunks, the one-token path the fusions run on),
and llama-bench ([rebased-b05204927.txt](benchmarks/inkling-2-mini-UD-Q8_K_XL/speedups/rebased-b05204927.txt)):

| model | KLD, batch 512 / 1 | same top token | tg128, upstream → branch | pp512 |
|---|---:|---:|---:|---:|
| Inkling-2-Mini UD-Q8_K_XL (R9700) | 0.0021 / 0.0018 | 97.7% / 98.2% | 31.0 → **53.9** | 815 → 853 |
| Qwen3.8-27B UD-Q6_K (both cards) | 0 / 0 | 100% / 100% | 24.13 → 24.14 | 943 → 944 |
| Gemma 4 12B BF16 (R9700) | 0 / 0 | 100% / 100% | 23.19 → 23.64 | 418 → 418 |

Qwen3.8 and Gemma compute the same perplexity on both builds to the fourth decimal (7.3932 and 672.3365 at batch
512), so the branch changes nothing they output; Gemma's 1.9% is the matvec grid padding. Inkling's KLD repeats
the original measurement to the sixth decimal. `test-backend-ops` on every changed op passes on the rebased
branch except the same `MUL_MAT` F16 case, which fails identically on plain upstream.

The router (`~/llama.cpp`, local branch `router` = upstream + these commits, plus the local thinking patch) now
builds from it: Inkling's presets generate at 50 tok/s through the server, against 29.5 on plain upstream.

## Caveats and what is left

- Only this card and these two backends were measured. No CUDA/NVIDIA, no Metal, no full-model CPU run.
- The branch was built on PR #32704, which mainline needs for these GGUFs; it was merged on 2026-11-22 and the
  branch now sits on upstream `b05204927` (see above).
- The code-quality run at reasoning effort 0.9 that this session set out to finish was stopped for this work and
  is still incomplete (see [code-quality-thinking.txt](benchmarks/inkling-2-mini-UD-Q8_K_XL/code-quality-thinking.txt)).
- About 2,100 kernels per token remain. The candidates left are each worth 1 to 2%: K/V norm + cache write,
  the controller's concat + down projection, residual adds, the per-layer state gather.

For upstream the commits split into general backend fixes (the RDNA4 grid padding, `TANH + MUL`, strided softcap,
the router's eps normalization, the `MUL_MAT_ID` scale alloc dep, same-vector matvec grouping), Inkling graph
changes, and Inkling-shaped fusions (conv step, depth mix, controller mix, relative bias) whose patterns would
need a maintainer's view on whether model-specific kernels belong in the CUDA backend.
