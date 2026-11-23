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
