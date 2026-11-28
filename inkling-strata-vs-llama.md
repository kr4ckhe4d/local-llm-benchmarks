# Inkling-2-Mini: what Strata does that llama.cpp doesn't

Measured 2026-11-23 on the R9700, same file for both engines (Unsloth `Inkling-2-Mini-UD-Q8_K_XL`): llama.cpp
db75ce3dc (upstream + the 16 [`inkling2-speedups`](inkling-2-mini-speedups.md) commits) against Strata 0.2.20's own
`strata-inkling` engine 0.1.66. Strata generates 68 tok/s through its server against llama.cpp's 53-54
([engine A/B](benchmarks/raw/engine-ab-inkling/README.md)). This page is why, and what llama.cpp could take from it.
Raw profiles and the timing patch: [benchmarks/inkling-2-mini-UD-Q8_K_XL/strata-vs-llama/](benchmarks/inkling-2-mini-UD-Q8_K_XL/strata-vs-llama/).

**Short answer: the weight reads cost the same in both; llama.cpp runs 2,138 kernels per token, Strata 915.** The
1,200 extra are the small "glue" ops between the matrix-vector products, about 2.5 ms of an 18.5 ms token. For
prompt reading at long context, llama.cpp is not slower per se: the 128K preset has to run 128-token batches because
of how the relative-position bias is allocated, and at 512-token batches it would read faster than Strata.

## Same bytes, so it is the engine

Strata reads this GGUF losslessly: the NVFP4 experts are repacked bit for bit into its SF4 layout, the four BF16
expert layers (20-23) run on "native GGUF_RAW kernels (zero S_K transcode)", and the trunk stays BF16. Both engines
read about 5.4 GiB per token (2.6 GiB trunk over 48 layer passes, 1.5 GiB NVFP4 and 0.5 GiB BF16 experts, 0.9 GiB
output head): an 8.4 ms floor at 640 GB/s.

## Where a token goes

llama.cpp: a temporary per-launch timer in the CUDA/HIP graph loop
([node-prof-timer.patch](benchmarks/inkling-2-mini-UD-Q8_K_XL/strata-vs-llama/node-prof-timer.patch),
`GGML_CUDA_NODE_PROF=1` with graphs off; it adds ~3.4 us per launch, subtracted below). Strata: its own
`STRATA_HIP_PROF=2` section timer, and its launches counted from `AMD_LOG_LEVEL=3`.

| per token, one token per step | llama.cpp | Strata |
|---|---:|---:|
| tok/s, no graphs (as profiled) | 51.9 | 62.4 |
| tok/s, graphs (llama-bench / Strata server) | 54.2 | 68 |
| kernel launches | **2,138** | **915** |
| weight matrix-vector products | 628 launches, ~13.7 ms | ~13 ms |
| everything else | 1,510 launches, ~5.6 ms | ~3 ms |

HIP graphs are worth 4% to llama.cpp (54.2 against 51.9), so the cost is not the CPU launching kernels: each small
kernel costs ~2-3 us on the GPU however it is launched (as found in the speedups work). The products themselves are
on par, section by section: output head 1.54 against 1.47 ms, MoE gate+up ~2.6 against 2.9 ms (Strata's includes
the activation), Q/K/V/R/gate projections ~4.1 against 3.8 ms. Strata's BF16 matvec is the same design as
`mul_mat_vec_f` (one wave per row, input in LDS, 16-byte loads); there is nothing to take there.

## The glue, part by part

Launches per token in each engine (llama.cpp from the timer's table, Strata from its kernel histogram and source,
`engine/src/inkling2/hip/ink_hip_backend.hip.cpp`):

| part of a layer | llama.cpp | Strata | how Strata does it |
|---|---:|---:|---|
| attention prep: K L2, V RMS, Q and R clip, rel-pos table and gather, PAD, K and V conv steps, output gate | ~456 | ~90 | `k2_qrkv_kvstore_relpos_fused`: all four norm/clips, the KV-cache store and the rel-pos bias in one kernel; `k2_shortconv4_kv_pair`: K and V conv in one launch; the sigmoid gate applied in the attention reduce |
| depth mix (block attention residuals) and the norms after it | ~360 | ~166 | `k1_attn_res_mix_norm_fused`: mix + the next RMS norm in one kernel; Q/K/V input norms as one 3-row launch (`k_rms_norm_rows3`); the block stack is a list of pointers, never concatenated |
| loop controllers (24 looped passes x 4) | ~288 | ~132 | the attn, K and V controllers of a pass batched per launch (`rms3`, `down_hiocc3`, `up3`); `[x, message]` read from two pointers, no CONCAT |
| MoE SITU activation | 192 | 0 | inside the gate+up kernel: each block computes rows j (gate) and j+inter (up) and writes the activation |
| MoE down, weighted sum, MLP conv, residual | ~180 | ~92 | `k_moe_reduce_sconv_add`: weighted sum + conv step + residual add in one kernel |
| attention-out conv, residual, block save | ~88 | 0 | in the output projection's write-out (`k_bf16_gemv1_wo_sconv`) |
| Q/K/V/R/gate/sink projections | ~124 | ~46 | one concatenated BF16 weight, one launch, results scattered straight to Q, R, gate, K, V and sinks (`k_bf16_gemv1_qkvrg`) |

## What llama.cpp could take, in order of payoff

1. **One attention-prep kernel** (~360 launches/token). Q mul+L2 clip, R mul+scale, K L2, V RMS and the rel-pos
   bias table are all per-head vectors of 16-128 values on the same token; one kernel with a block per head can do
   them all, and could write K/V straight into the cache (the `SET_ROWS`). The two K and V conv steps already have a
   fused one-token kernel; give it two inputs.
2. **SITU in one kernel** (144-192 launches). Today: gate_up product with scale, `SCALE..SCALE` twice, `UNARY..MUL`,
   `MUL`. A single elementwise SITU kernel over the fused gate_up output removes three of the four; folding it into
   the `MUL_MAT_ID` write-out (Strata's way) removes all four but needs gate and up rows computed by the same block.
3. **MoE tail in one kernel** (~90-130 launches): `MUL..ADD` (weighted sum), `CONCAT..SCALE` (MLP conv step) and
   `ADD ffn_inp` are three passes over the same 2,304 values.
4. **Controllers batched** (~150 launches): the attn, K and V controllers of a pass share their input; one launch
   per stage for all three, and the `CONCAT [4608]` of `[x, message]` dropped by passing both as sources.
5. **Depth mix fused with the norm after it**, and the Q/K/V input norms as one launch (~190 launches).
6. **Attention-out conv and residual after `wo`** (~90 launches) as a `MUL_MAT..(conv step)` epilogue fusion,
   like the existing `MUL_MAT..ADD`.

At ~2.5 us each, 1,100 fewer kernels is ~2.5-3 ms a token: llama.cpp at roughly 62-66 tok/s, near Strata's 68. Each
item fits the pattern of the 16 existing commits (a graph match in `ggml_cuda_try_fuse` plus a kernel, with a
`test-backend-ops` case).

## Prompt reading: the batch size, not the engine

At a 512-token prompt the two read at the same speed (llama.cpp pp512 853, Strata 836 tok/s). At depth the A/B
showed llama.cpp 510 against 643 (33K) and 407 against 541 (125K), but that llama.cpp ran the 128K preset's `-ub 128`:

| llama.cpp, pp2048 at 32K depth | tok/s |
|---|---:|
| `-ub 128` (the 128K preset) | 531 |
| `-ub 512` (the 32K preset) | **679** (+28%) |
| `-ub 1024` | does not fit |

`-ub 512` beats Strata's 643, but a 128K server cannot use it: the compute buffer is 23.4 GB at `-ub 512` and
11.7 GB at `-ub 256` (both fail to load), about 350 bytes per query-key pair. The prompt-batch rel-pos bias in
`src/models/inkling2.cpp` is a `get_rows` into an F32 `[n_kv, n_head, n_tokens]` tensor plus a permuted `cont` copy
for flash attention. The speedups work already fuses that into one F16 mask at run time (the global layers' masks
cost ~0.17 ms per batch, under 1%), but the graph allocator still reserves the unfused F32 intermediates at full
size. Strata hands its attention kernel the `[n_head, 1025]` table and looks the bias up per (query, key) inside it.

7. **Build the prompt-batch bias in F16 in the graph itself** (or pass the table to `FLASH_ATTN_EXT` and gather in
   the kernel), so only one 48-byte-per-pair tensor, or none, is allocated. That should let the 128K preset use
   `-ub 512`: +28% prompt reading at 32K. At ~30K depth the batch time is otherwise flash attention (19%) and the MoE
   products, not the mask.

## Not a lever

- Long-context generation: equal at 125K (34.8 against 34.2 tok/s).
- Strata's NVFP4 kernel keeps activations in F16 and decodes E2M1 pairs through a 256-entry LUT with `fdot2`, while
  llama.cpp's MMVQ path (`vec_dot_nvfp4_q8_1`) quantizes the activation to Q8_1 first, in a second kernel inside the
  same op (so llama.cpp's true kernel count is ~100 above the 2,138 graph launches). The MoE products time the same
  either way, so this is a difference in style, not speed.
- Strata's DSpark drafter: slower than no drafter except on code ([A/B](benchmarks/raw/engine-ab-inkling/README.md)).

## Tried on a branch

All seven items above, on the llama.cpp branch `inkling2-strata-ideas` (in `~/llama.cpp-inkling`, cut from
`inkling2-speedups` db75ce3dc, pushed to the fork `kr4ckhe4d/llama.cpp`). Since 2026-11-23 the router builds it and
its 128K Inkling preset uses `-ub 512`. Todo, per-step numbers, test script and patches:
[benchmarks/inkling-2-mini-UD-Q8_K_XL/strata-ideas/](benchmarks/inkling-2-mini-UD-Q8_K_XL/strata-ideas/TODO.md).
Every step was checked against the branch start's logits (wiki.test.raw, -c 512, batch 512 and batch 1): **KLD 0 and
100% same top token after each one**, so the fused kernels repeat the unfused arithmetic exactly. Each has a
`test-backend-ops` case.

| commit | change | kernels / token | tg128 |
|---|---|---:|---:|
| start | | 2,138 | 53.97 |
| `55da13d05` | new op `GGML_OP_REL_BIAS`: the prompt-batch bias as one op, so only its F16 mask is allocated (item 7) | 2,138 | 53.94 |
| `fa48751bb` | Q/K/V/R norms and clips plus both KV-cache stores as one kernel (item 1) | 1,876 | 56.14 |
| `c6f75a9da` | SITU as one element-wise kernel (item 2) | 1,732 | 57.29 |
| `cdd14ad79` | loop controllers in batches of up to four, no `CONCAT` (item 4) | 1,500 | 59.01 |
| `443335b67` | the layer residual inside the conv step (items 3, 6) | 1,412 | 59.94 |
| `260261708` | the RMS norm after a depth mix inside the mix kernel (item 5) | 1,329 | 60.59 |
| `1e296bb7b` | the MoE weighted sum inside the FFN-out conv step (item 3) | 1,281 | 61.00 |
| `712d4ab2e` | the `wo` product, its conv step and the residual as one kernel (item 6) | **1,233** | **62.06** |

**+15% generation (54.0 -> 62.1), 42% fewer kernels, and the 128K context now fits `-ub 512`.** A 128K server
needed 23.4 GB of compute buffer at `-ub 512` before; now it loads in 29.5 GB on the card (and `-ub 128` needs 4.7 GB
less). Through the server, against the same Strata numbers as above (the branch measured at `89edf0c8a`, before the
last fusion):

| tok/s | llama.cpp start (`-ub 128`) | branch (`-ub 512`) | Strata |
|---|---:|---:|---:|
| generation, empty context | 53.2 | **59.8** | 68.0 |
| 33K prompt: reading / generating | 510 / 46.6 | **716** / 51.5 | 643 / **54.6** |
| 125K prompt: reading / generating | 407 / 34.8 | 532 / **37.8** | **541** / 34.2 |

llama.cpp now reads a 33K prompt 11% faster than Strata and is level at 125K, and generates 11% faster than Strata
at 125K. Strata still generates ~14% faster in an empty context and 6% at 33K.

Two things worth knowing from doing it:

- **The first attention-prep kernel raced, and only the KLD check caught it** (0.0016, which looks like rounding
  noise). Unfused, K's and V's F32 results die before R is computed, so the allocator gave R their memory; a kernel
  writing all three at once overwrote R. It now skips the F32 K/V writes nothing reads, and every fusion here checks
  its outputs against each other as well as against its inputs. Matching the unfused arithmetic exactly (down to
  `rms_norm`'s four-values-per-lane loop, `mul_mat_vec_f`'s block size and the RDNA4 grid padding) is what made a KLD
  of exactly 0 the pass mark, so a race cannot hide.
- **The controllers' 64-row down product ran at ~100 GB/s**: 64 blocks on a 64-CU card. Batching the Q, K and V
  controllers gives each launch three times the blocks as well as removing launches.

The router's other models are unaffected (checked at 4 commits; the later fusions match only Inkling's patterns):
Gemma 4 12B BF16 and Qwen3.8-27B Q6 give KLD 0 against the router build at both batch sizes, tg128 23.65 / 23.65
and 24.12 / 24.11. The per-request thinking check passes on the router build. Not done: the three Q/K/V input norms
of the full-attention passes as one launch (~16 kernels); the F32 router product (128 rows at ~200 GB/s); a `PAD` of a
constant weight and a conv-state `GET_ROWS` every pass. `GGML_OP_REL_BIAS` has CPU and CUDA/HIP versions only; Vulkan
would fall back to the CPU for it.

## Rebased onto upstream 15fcfc735 (2026-11-27)

Upstream landed its own Inkling 2 fusions in the four days to 2026-11-26 — `0e4e925e8`, `51ab45e3c`,
`abca69200`, `e683365a7`, `396ed2cce`, by three authors, none of them this repo — and moved its fusion
dispatch out of `ggml-cuda.cu` into a new `fusion.cu`. **They do not reach these numbers on RDNA4:**
plain upstream generates **39.52 tok/s** on the same GGUF and flags where this branch reaches 63.21, so
the branch was rebased rather than retired. 17 of its 29 commits had to have their hooks re-homed into
`fusion.cu`; the recipe is in llama.cpp `ae2fa1043`.

The rebase landed at 59.33 tok/s, 4.5% below the 62.13 it replaced, and the launch counter found both
causes at once — 1,537 launches a token against 1,233:

| | tok/s | launches/token |
|---|---:|---:|
| pre-rebase `5c9e1f761` | 62.13 | 1,233 |
| rebased `ae2fa1043` | 59.33 | 1,537 |
| + the state-cell guard `4b02a212c` | 60.67 | 1,441 |
| + the dispatch order `484c0fa9a` | **63.21** | **1,185** |
| plain upstream `15fcfc735` | 39.52 | — |

- **Upstream `7b74cb92d` reads recurrent states in place instead of copying**, so the one-token conv step's
  state cell and the history window it reads became views of the same `cache_r_l*` tensor. The memory guard
  refused `wo_conv` and `moe_conv_step` on every layer, 96 launches a token, which stopped the attention-out
  projection and the MoE weighted sum folding into the step. That pair is the rolling state itself — the
  kernel loads the window before it stores the cell — so it is now skipped and every other pair still checked.
- **Re-homing inverted two matchers.** The generic `MUL -> L2_NORM` fusion ended up ahead of `attn_prep`,
  matched `Qcur`'s `MUL` first and returned, so the per-head prep never saw the node and Q, K, V and R each
  ran their own kernel. Relative order inside `ggml_cuda_try_fuse` is load-bearing; the pre-rebase file is
  the reference for it.

`ub1` KLD stays 0.000000 at 100% same-top-p through both fixes. The end state is **48 launches below where
the branch sat before the rebase**, because upstream removed launches of its own as well.

**The other models are not untouched by the rebase, and the branch is not Inkling-only.** Generation,
three builds, [`benchmarks/.../strata-ideas/other-models.sh`](benchmarks/inkling-2-mini-UD-Q8_K_XL/strata-ideas/other-models.sh):

| tg128 | pre-rebase `b93bef94f` | plain upstream `15fcfc735` | branch `484c0fa9a` |
|---|---:|---:|---:|
| Gemma 4 12B BF16, R9700 | 23.69 | 23.31 | **23.73** |
| Qwen3.8-27B Q6, two cards | 24.12 | 24.69 | **24.70** |

Qwen3.8 gains 2.4% and it is upstream's doing. Gemma 4 looks flat, but plain upstream loses 1.6% on it and
the branch wins that back: **+1.8% against upstream**, from the generic fusions (TANH+MUL, the consecutive
matvec grouping, `MUL -> L2_NORM`), not the Inkling-shaped ones. The two fixes above cannot touch either
model — both matchers need an `SSM_CONV` node these dense architectures do not build.

KLD was not re-measured for the other two: the saved bases under `/mnt/fast/kld-inkling/strata-ideas/` were
captured on `db75ce3dc`, so after a rebase they no longer isolate the branch from upstream's own drift.

**Against Strata, served, at 128K** ([`engine-ab-inkling`](benchmarks/raw/engine-ab-inkling/README.md#re-run-2026-11-28-the-rebased-branch-against-strata-0222),
same client and GGUF as above, Strata updated to 0.2.22 / engine 0.1.69 the same day):

| | branch before | branch rebased | Strata 0.2.20 | Strata 0.2.22 |
|---|---:|---:|---:|---:|
| generation, empty context | 59.7 | **61.7** | 68.5 | 68.1 |
| 33K prompt: reading / generating | 716 / 51.5 | 711 / 52.5 | 643 / 54.6 | 642 / 54.6 |
| 125K prompt: reading / generating | 532 / 37.8 | 523 / 38.5 | 541 / 34.2 | 540 / 34.2 |

Strata did not move across three engine versions. The branch gained ~3% generating and lost 1.7% reading the 125K
prompt; the next section finds where that went, and wins it back with more. The empty-context gap is now about 10%, down from 14% at 7 commits. Through the
server the branch generates 61.7 where `llama-bench` says 63.2: the server holds a 128K context and samples.

## The 125K reading dip, and prompt batches through upstream's depth mix (2026-11-28)

**The dip is real and it is flash attention.** A whole 125K prompt in `llama-bench` (R9700, `-fa 1 -ub 512
-b 2048`), the two builds alternated twice: pre-rebase `b93bef94f` 573.6 and 573.5 tok/s, rebased `484c0fa9a`
562.5 and 562.5, 1.9% lower. At depth 0 the two are equal (902 against 903), so it grows with the context. The
per-launch timer (`strata-vs-llama/node-prof-timer.patch`, ported to the new dispatch site) on 512-token batches
at 64K depth puts it in one op: `FLASH_ATTN_EXT` 437 ms against 476 (+39), while the MoE products got 23 ms
faster and the lost `SSM_CONV`+`SCALE` prompt fusion cost about 10. The FA sources on the branch are byte-for-byte
upstream's, and the only FA change across that rebase is upstream's loader refactor and indexed bias (#32901,
#33063), so that is the likely cause; I did not run the old kernel against the new graph to prove it. It is not
a general regression: Gemma 4 at 32K depth reads at 328 tok/s on all three builds. Routing Inkling's prompt
batches through upstream's indexed-bias FA instead of the branch's `REL_BIAS` mask was 2% slower (540 against 552),
so that is not the fix.

**The bigger finding was beside it.** Plain upstream read faster than the branch at every depth (983 against 903
at depth 0) without faster attention: its FA is the slowest of the three (510 ms). The branch builds the depth
mix (attention over the earlier block outputs) in the shape its one-token kernel wants, transposed stacks with the
states on the left of the second product. For 512 tokens that runs as matrix products with 2 to 5 columns per token,
plus the `CONCAT`s that build the transposed stacks: about 150 ms per batch at 64K depth, where upstream builds
the same math in the node order its fused `depth_mix` kernel (#33060) takes, in 30-40 ms. Commit `d5adb4cb5` builds
prompt batches in upstream's order and permutes the multi-query results back for the callers; one-token graphs are
unchanged.

`llama-bench` on the R9700, Q8 GGUF: pre-rebase `b93bef94f`, plain upstream `15fcfc735`, branch `484c0fa9a`,
the same with the depth-mix fix, and that rebased onto upstream `8e23278c7`:

| tok/s | pre-rebase | upstream | branch | + fix | rebased |
|---|---:|---:|---:|---:|---:|
| pp2048, empty | 902 | 983 | 903 | 968 | **989** |
| pp2048 at 32K depth | 687 | 716 | 678 | 724 | **725** |
| whole 125K prompt | 573.6 | 578.3 | 562.5 | 590.0 | **589.9** |
| tg128 | | | 63.21 | 63.12 | 63.19 |

The 125K prompt now reads 2.8% faster than before the first rebase and 4.9% faster than yesterday; generation
did not move. KLD against fresh base logits from `484c0fa9a`: `-ub 1` mean 0.000000 at 100% same top token, as
at every earlier step; `-ub 512` mean 0.0019 at 98.2% same top, perplexity ratio 1.0011 ± 0.0013. That is
rounding, not a mismatch: with the fused kernel switched off the new graph alone gives 0.0013 (a softmax over the
states in a different order, different product kernels), and the previous rebase moved the same number by the
same 0.0019. Upstream's `DEPTH_MIX` op tests pass, including the multi-token cases.

The branch was then rebased onto upstream `8e23278c7` (9 commits, among them #28898, which moved weight scales
onto the matmul itself and made the branch's scaled-`MUL_MAT_ID` alloc dep obsolete; removed in `f60336b90`).
Every number above holds on it. Served numbers against Strata were not re-run.

