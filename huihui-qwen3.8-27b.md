# Huihui-Qwen3.8-27B-abliterated: speed and recall as context grows, to 256K

Measured 2026-11-21 on the two-card box in `README.md` (RX 9070 XT + R9700,
ROCm), llama.cpp `29b52d398`. Data:
[`benchmarks/huihui-qwen3.8-27B-UD-Q6_K_XL/`](benchmarks/huihui-qwen3.8-27B-UD-Q6_K_XL/),
with the stock comparison in
[`benchmarks/qwen3.8-27B-UD-Q6_K/`](benchmarks/qwen3.8-27B-UD-Q6_K/).

[`huihui-ai/Huihui-Qwen3.8-27B-abliterated`][card] is Qwen3.8-27B with refusals
abliterated out of layers 17-52. The `UD-*` files in its GGUF repo are built
from `unsloth/Qwen3.8-27B-GGUF`, and the card says the MTP head and vision tower
were left alone. The file used here is `UD-Q6_K_XL` (24.8 GB on disk, 1.7 GB
more than the stock `UD-Q6_K`). It carries the MTP layer (`blk.64`, 15 tensors,
`nextn_predict_layers = 1`), so the `draft-mtp` presets work unchanged.

[card]: https://huggingface.co/huihui-ai/Huihui-Qwen3.8-27B-abliterated-GGUF

## Setup

Both models are served by themselves with the flags of the `-q6-128k` presets:
`-c 131072 -ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0 --spec-type draft-mtp`,
`templates/qwen38-late-system.jinja`, `--load-mode dio --ctx-checkpoints 4`.
`throughput-test.py --runs 2 --depth N` puts N tokens of code-shaped filler
ahead of the usual 700-token generation prompt (temperature 0, thinking off,
prompt cache off). Runs repeat to within 0.3 tok/s, so n=2 is enough.

## Speed

| depth (tokens) | Huihui tg | stock tg | Δ tg | Huihui prefill | stock prefill | Δ prefill | MTP accept (H / S) |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 54 | 55.88 | 57.97 | -3.6% | 315 | 314 | — | 86.0 / 84.3% |
| 16,852 | 51.22 | 52.87 | -3.1% | 1,138 | 1,006 | +13.0% | 86.3 / 84.6% |
| 34,452 | 46.77 | 48.27 | -3.1% | 1,049 | 939 | +11.7% | 86.9 / 85.5% |
| 69,652 | 39.68 | 40.70 | -2.5% | 911 | 828 | +10.0% | 87.7 / 86.6% |
| 119,572 | 31.42 | 32.23 | -2.5% | 766 | 707 | +8.3% | 85.2 / 85.1% |

* **Both models lose 44% of their generation speed between an empty context
  and 120K** (Huihui 55.9 to 31.4, stock 58.0 to 32.2). The curve is the
  same shape for both. The cost comes from attention over the KV cache, not
  from the weights.
* **Huihui generates 2.5-3.6% slower.** It reads 8% more weight bytes per
  token. Its MTP acceptance is 1-2 points higher, which recovers part of that.
* **Huihui prefills 8-13% faster**, although its file is larger. Not
  investigated. The tensor types differ a lot. Huihui has 271 Q8_0 tensors
  against stock's 154, and it has no Q5_K-heavy or IQ4 mix: 89 tensors move
  Q6_K to Q8_0 and 28 move Q5_K to Q8_0. The extra Q8_0 matmuls may run
  faster in prompt processing than the K-quants they replace, but that hasn't
  been tested. A full 119.6K prompt takes 156 s on Huihui and 169 s on stock.
* MTP acceptance does not fall with depth on either model (85-88%), so the
  drafter is worth as much at 120K as it is at the start.

## Recall at ~117K tokens

| probe | Huihui | stock |
|---|---|---|
| `needle-test.py --depth 110000 --no-think` (verbatim, 117,516 tokens) | 5/5 | 5/5 |
| `semantic-recall-test.py --depth 100000 --no-think` (by meaning, 117,170 tokens) | 5/5 | 5/5 |

Every needle passes at 5%, 25%, 50%, 75% and 95% of the context. The
abliteration did not cost any long-context recall these probes can detect.
Both probes saturate at this depth, so this shows there is no damage. It does
not rank the two models.

## Out to 256K

The `huihui-qwen3.8-27B-abliterated-q6-256k` preset uses the 128K flags with
`-c 262144`. Loaded, it leaves 2.8 GB free on the 9070 XT, the tighter card,
and 5.4 GB on the R9700 (`rocm-smi`, desktop included). Huihui only, one timed
run per depth, because the 128K runs agreed to within 0.3 tok/s. The filler
overshoots the requested depth by ~8%, so the 240K request built a
260,672-token prompt, 1.5K short of the context.

| depth (tokens) | tg | prefill | full-prompt prefill | MTP accept |
|---:|---:|---:|---:|---:|
| 119,572 | 31.42 | 766 | 2.6 min | 85.2% |
| 171,530 | 26.30 | 658 | 4.3 min | 84.0% |
| 216,184 | 23.47 | 585 | 6.2 min | 85.7% |
| 260,672 | 20.94 | 528 | 8.2 min | 85.2% |

| probe | result |
|---|---|
| `needle-test.py --depth 222000 --no-think` (240,610 tokens) | 5/5 |
| `semantic-recall-test.py --depth 205000 --no-think` (243,137 tokens) | 5/5 |

* **The decline slows with depth.** Generation drops 44% over the first 120K
  and another 33% over the next 140K, ending at 37% of the empty-context speed.
  Prefill falls more gently, from 1,138 to 528 tok/s.
* **Recall holds at 240K**, at every position from 5% to 95%. These probes
  saturate, so they show no damage and do not rank models.
* **The cost of 256K is latency.** A full prompt takes 8 minutes before the
  first token. Generation still runs at 21 tok/s. In an agent loop each turn
  only prefills what it appends, so the 8 minutes is paid once.

Use 128K unless a job needs more. 256K works, and an unused context costs only
VRAM.

## Agentic coding

On [agent-eval](agent-eval.md) (21 tasks in a sandboxed tool loop, hidden tests, 3
repeats, thinking off), Huihui and stock Qwen3.8 both pass 42 of 63 runs. Huihui makes 6
false claims of done against stock's 4; stock runs out of turns more often. Abliteration
shows no cost here.

## Not measured

Refusal rate, one-shot code quality, KLD against the stock model,
anything with thinking on, and stock Qwen3.8 past 120K.
