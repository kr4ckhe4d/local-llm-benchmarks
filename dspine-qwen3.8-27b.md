# DSpine for Qwen3.8-27B: a partial port, and why it loses

Measured 2026-11-09 on the two-card box in `README.md` (RX 9070 XT + R9700,
ROCm), llama.cpp build 12165 (`4b77dee05`). Data:
[`benchmarks/qwen3.8-27B-dspine-b16/`](benchmarks/qwen3.8-27B-dspine-b16/).

[`tencent/Qwen3.8-27B-DSpine-b16`][card] is not a model to chat with. It is a
**2B speculative-decoding drafter** for Qwen3.8-27B, the same job as DFlash2
(`dflash2-qat-q2.md`) and the in-file MTP head the `qwen3.8-*` presets use. The
card claims 15-25% longer acceptance than DFlash2 (HumanEval 5.71 vs 4.87 tokens
per step at T=0) and 2.7-3.8x end-to-end on agent replays.

[card]: https://huggingface.co/tencent/Qwen3.8-27B-DSpine-b16

## It cannot run as released on this box

* Tencent's runtime is an **SGLang 0.5.22 plugin that requires CUDA**, launched
  with FlashAttention 3 (Hopper-only). The other path in the repo is MLX (Apple).
* **llama.cpp has no DSpine support**: nothing on master as of 2026-11-09, and no
  open PR or issue for it.

The config still says `"architectures": ["DFlashDraftModel"]`, and most of the
checkpoint is a plain DFlash v1 drafter: `fc` (5 target layers x 5120 -> 5120),
five Qwen3 layers with an 8,192-token sliding window, and a norm. The new part
is `selected_prefix_bridge.*`, 13 tensors and 296M of the 2.03B parameters:
a 248,320 x 1,024 codebook plus read/write/gate projections that pass each draft
position's predicted predecessor features to its neighbour, layer by layer.
That bridge is the paper's contribution. llama.cpp has nothing that would run it.

## The partial port

1. `scripts/strip_bridge.py` copies the checkpoint without the bridge and the
   0-d version scalars: 58 tensors, 1.73B params kept; 13 tensors, 296M dropped.
2. Stock `convert_hf_to_gguf.py --target-model-dir <Qwen3.8-27B tokenizer>
   --outtype q8_0` accepts it as `dflash` (1.84 GB). DFlash2 converted the same
   way for the comparison (2.05 GB).
3. Served with `--spec-type draft-dflash --spec-draft-ngl 999`, target
   `Qwen3.8-27B-UD-Q6_K`, 32K, q8_0 KV, `-np 1`, `-ub 1024`.

**The in-block causal mask is not honoured.** DSpine is trained with
`draft_block_causal` and the converter writes `dflash.attention.causal = true`.
Overriding it to `false` produced *identical* accepted-token counts on every
prompt (411/1435, 350/1736, 300/1985 at n=5), so llama.cpp's DFlash graph does
not read the flag and always drafts the block non-causally. Every DSpine row
below therefore differs from the trained model in two ways: no bridge, and a
non-causal block.

## Results

Three prompts (code: the README's LRU-cache prompt; math: a multi-step word
problem; chat: a travel itinerary), 700 tokens, temp 0, thinking off, n=2.
Greedy decoding made both runs identical for every drafter except MTP, whose
accepted counts differed slightly between runs, so each cell is effectively one
sample. Cells are the mean of the two runs. Tokens per step is estimated as `(accepted + rounds) / rounds` with
`rounds = drafted / n_max`, which assumes every round drafts the full block.

| Drafter | n_max | Code tok/s | Math tok/s | Chat tok/s | Code accept | Code tok/step |
|---|---:|---:|---:|---:|---:|---:|
| none | — | 23.62 | 23.62 | 23.61 | — | 1.00 |
| MTP (in-file head) | 3 | 57.84 | 54.34 | **42.57** | 84.3% | 3.53 |
| **DFlash2** | 5 | **74.33** | **60.12** | 41.02 | 80.6% | 5.03 |
| DFlash2 | 7 | 72.00 | 53.04 | 36.02 | 71.9% | 6.03 |
| DSpine, no bridge | 3 | 41.05 | 37.61 | 29.65 | 46.5% | 2.40 |
| DSpine, no bridge | 5 | 36.28 | 29.93 | 26.21 | 28.6% | 2.43 |
| DSpine, no bridge | 7 | 29.13 | 25.50 | 21.40 | 20.5% | 2.43 |
| DSpine, no bridge | 15 | 34.16 | 27.12 | 24.58 | 9.8% | 2.47 |

**Stripped DSpine accepts the same ~410 tokens per 700 whatever the block
size**: 407 at n=3, 411 at n=5, 414 at n=15. It predicts roughly the first
1.4 positions of each block and almost nothing after. That is the expected
shape if the bridge is what carries information along the block: without it,
the plain DFlash layers see only the anchor and the target features, and later
positions go to chance. At its best (n=3) it is 1.74x over no drafter on code,
but behind MTP and DFlash2 on all three prompts.

(n=15 is faster than n=7 at the same tokens per step, 2.47 against 2.43. Not
investigated; both are well below n=3.)

Side results on the drafters that do work, the first DFlash2 numbers on two cards
and the Q6_K target:

* **DFlash2 at n_max 5 is the fastest drafter here on code and math**: 74.3 tok/s
  against MTP's 57.8 (1.29x) and 3.15x over no drafter. n_max 7 drafts more
  but accepts less and is slower everywhere, matching the n_max-5 sweet spot
  `dflash2-qat-q2.md` found on one card.
* **On open-ended chat MTP wins** (42.6 vs 41.0): DFlash2's acceptance falls to
  35% on prose, against MTP's 53%.

## Verdict

* **The bridgeless port is not usable**: it loses to both existing drafters on
  every prompt. Both converted GGUFs were deleted afterwards; `scripts/` rebuilds
  them in a few minutes from the Hugging Face checkpoints.
* **The card's claim is untested here, not refuted.** Measuring it needs the
  bridge (and a causal block) implemented in llama.cpp's DFlash graph.
* **Worth acting on now**: DFlash2 n_max 5 beats the presets' MTP by 29% on code
  on the Q6_K target. A `qwen3.8-27B-q6-*` DFlash2 preset is the obvious
  follow-up (VRAM at 128K/256K not yet measured).

## Reproduce

`benchmarks/qwen3.8-27B-dspine-b16/scripts/`: `strip_bridge.py` (run it with
any Python that has `torch` and `safetensors`), `sweep.sh` (all configs; set
`S=` for the output dir), and `specbench.py` (one config against a running
server). Raw per-run timings are in `spec-sweep.jsonl`.

Lesson from the run: a llama-server left over from a smoke test kept the port.
Every new server then failed to bind, and the benchmark silently measured the
old one. `sweep.sh` now refuses to start while the port is busy and checks
its own server is alive before measuring.
