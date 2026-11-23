# Inkling in llama.cpp: ideas taken from Strata (branch `inkling2-strata-ideas`)

Branch in `~/llama.cpp-inkling`, cut from `inkling2-speedups` db75ce3dc on 2026-11-23. Source of the ideas:
[inkling-strata-vs-llama.md](../../../inkling-strata-vs-llama.md). Local only, nothing pushed.

Every item: test-backend-ops case against CPU, KLD against the branch start's logits (wiki.test.raw, -c 512,
batch 512 x 16 chunks and batch 1 x 4 chunks; the noise floor is the start build's own batch-1 vs batch-512
difference, KLD ~0.0017), `llama-bench -fa 1 -lm dio` tg128 on the R9700 (ROCm1), launches per token from the
node timer (`../strata-vs-llama/node-prof-timer.patch`, applied only for measuring, never committed).

Start: tg128 54.15 tok/s, 2,138 launches per token; pp2048 @ d32768 531 tok/s (ub 128), 679 (ub 512); a 128K
context needs 23.4 GB of compute buffer at ub 512.

## Items, in order

- [x] **0. Baseline**: build the branch start, save KLD base logits (ub 512, ub 1), record tg128 / pp / launches.
- [x] **1. Prompt-batch rel-pos bias memory.** Done: `55da13d05`, new op `GGML_OP_REL_BIAS`. Make the 128K context fit `-ub 512` (or 256): build the bias so only
      the F16 mask is allocated at n_kv x n_tokens x n_head, not the F32 gather + permuted copy. Measure compute
      buffer at 128K and pp2048 @ d32768.
- [x] **2. Attention prep in one kernel** Done: `fa48751bb` (6 launches per pass -> 1, K/V written straight to the cache). (~360 launches): Q mul+L2 clip, R mul+scale, K L2, V RMS (+ K/V conv
      steps as one launch with two inputs).
- [x] **3. SITU in one kernel** Done: `c6f75a9da` (4 launches per pass -> 1, prompt batches too). (~150-190): the `SCALE..SCALE`, `UNARY..MUL`, `MUL` after the gate_up product.
- [x] **4. MoE tail in one kernel** Done: `443335b67` (residual into the conv step) + `1e296bb7b` (weighted sum into it too): sum, conv, state store and residual are one kernel.
- [x] **5. Loop controllers batched** Done: `cdd14ad79` (12 launches per looped pass -> 4; the 64-row down product was at ~100 GB/s). (~150): attn/K/V controllers of one pass in one launch per stage, no CONCAT.
- [x] **6. Depth mix + following RMS norm** Done (91 places, one query). Not done: the three Q/K/V input norms of the full-attention passes as one launch.
- [x] **7. Attention-out conv + residual after `wo`** Done: `443335b67` + `712d4ab2e` (the `wo` product, its conv step and the residual as one kernel).

## Results

| step | tg128 | launches / token | KLD ub512 / ub1 | notes |
|---|---:|---:|---|---|
| start (db75ce3dc) | 53.97 | 2,138 | 0 / 0 (base) | pp2048 @ 32K: 531 (ub 128), ub 512 does not fit 128K |
| 1 `55da13d05` REL_BIAS op | 53.94 | 2,138 | 0 / 0 | 128K loads at ub 512 (29.5 GB); pp2048 @ 32K 531 -> 681, @ 96K 398 -> 468 |
| 2 `fa48751bb` attention prep | 56.14 | 1,876 | 0 / 0 | first try raced (R output placed over dead K/V, KLD 0.0016); fixed by not writing them |
| 3 `c6f75a9da` SITU | 57.29 | 1,732 | 0 / 0 | |
| 5 `cdd14ad79` controllers batched | 59.01 | 1,500 | 0 / 0 | |
| 4/7 `443335b67` residual in conv step | 59.94 | 1,412 | 0 / 0 | the next layer's state gather moved out from between |
| 6 `260261708` depth mix + norm | 60.59 | 1,329 | 0 / 0 | |
| 4 `1e296bb7b` MoE sum into conv step | 61.00 | 1,281 | 0 / 0 | |
| 7 `712d4ab2e` wo + conv step | **62.06** | **1,233** | 0 / 0 | the branch tip (+ `b9264d93c`, test registration) |

Through the server (`../../raw/engine-ab-inkling`, 128K context, the branch at `-ub 512`; first at 4 commits
(`cdd14ad79`, rows in `results-branch-4commits.jsonl`), then at 7 (`89edf0c8a`, before the `wo` fusion):

| | start (`-ub 128`) | 4 commits | 7 commits | Strata |
|---|---:|---:|---:|---:|
| generation, empty context (code / prose / explain) | 53.1 / 53.2 / 53.3 | 57.8 / 57.8 / 57.9 | 59.7 / 59.7 / 59.9 | 67.8 / 68.5 / 67.8 |
| 33K prompt: prefill / decode | 510 / 46.6 | 716 / 49.7 | 716 / 51.5 | 643 / 54.6 |
| 125K prompt: prefill / decode | 407 / 34.8 | 530 / 36.2 | 532 / **37.8** | 541 / 34.2 |

Other models (`other-models.txt`, against `~/llama.cpp` at the branch start): Gemma 4 12B BF16 and Qwen3.8-27B Q6
KLD 0 at -ub 512 and -ub 1, tg128 23.65 / 23.65 and 24.12 / 24.11.

Since 2026-11-23 the router (`~/llama.cpp`, branch `router`) runs this branch, and the 128K preset uses `-ub 512`.
Rebased the same day onto upstream `44d50873b` (all 28 commits, speedups included; tip `5c9e1f761`, force-pushed to
the fork): tg128 62.13, KLD 0 against the branch start at both batch sizes, all fusion tests pass, thinking check ok.

Open: the three Q/K/V input norms of the full-attention passes as one launch (~16 launches); the router weight is F32 and its 128-row product runs at
~200 GB/s; `PAD` of a constant weight and the conv-state `GET_ROWS` run every pass (~72 launches).
