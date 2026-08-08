# Local LLM Benchmarks — CachyPC

**Hardware:** AMD Ryzen 9 5950X (16C/32T) · AMD RX 9070 XT (gfx1201, RDNA4,
16304 MiB VRAM) · 64GB DDR4-3200 dual-channel · `llama.cpp` b8918.

**Backend: use the ROCm build at `~/llama.cpp/build/bin/`.** Not
`build-vulkan/`. See below — this is the single biggest win on this machine.
Switching script: `~/llama.cpp/switch-model.sh`.

---

## Headline: the ROCm build is ~2x faster than Vulkan

Same model, same flags, same benchmark (`llama-bench`, `pp4096`/`tg64`, `-r 2`):

| Backend | Config | Prompt tok/s | Gen tok/s |
|---|---|---|---|
| Vulkan (`build-vulkan/`) | `-ncmoe 40 -ub 512` | 333.4 | 29.3 |
| ROCm (`build/`) | `-ncmoe 40 -ub 512` | 706.0 | — |
| ROCm (`build/`) | `-ncmoe 24 -ub 1024` | **1616.2** | **39.0** |

Backend swap alone is **2.1x** on prompt processing. With `-ncmoe` and `-ub`
tuned on top, **4.8x prompt / +33% generation** versus the old Vulkan config.
Both builds already exist; `build/` is `GGML_HIP=ON` with
`AMDGPU_TARGETS=gfx1201`.

**Every Vulkan number in the old version of this file is superseded.** They are
kept at the bottom for reference only.

---

## Why 1M context is possible at all: hybrid attention

Qwen3.6-35B-A3B (`qwen35moe`) and Qwen3-Coder-Next (`qwen3next`) are **hybrid
attention** models. `full_attention_interval = 4` means only every 4th layer
keeps a KV cache; the rest are SSM/gated-linear layers with a **constant-size
recurrent state** that does not grow with context.

| Model | Layers | Layers with KV | SSM state | KV @1M (q8_0) |
|---|---|---|---|---|
| Qwen3.6-35B-A3B | 40 | 10 | 62.81 MiB | 10,880 MiB |
| Qwen3-Coder-Next | 48 | 12 | 75.38 MiB | 13,056 MiB |

Both use 2 KV heads × 256 key/value length — tiny per-layer KV on top of the
1-in-4 layer count.

**This is the whole reason 1M fits in 16GB.** A conventional full-attention
coder such as Qwen3-Coder-30B-A3B has KV on all 48 layers with 4 KV heads ×
128 dim ≈ 52 KB/token → **~52 GB of KV at 1M**. Not runnable here at any
quant. When shopping for long-context models on this box, check
`full_attention_interval` in the GGUF metadata first; parameter count matters
far less than attention topology.

### The 1M coding recommendation

**Qwen3-Coder-Next, already on disk.** It is the only coding-specialist model
with the hybrid architecture that makes 1M viable in 16GB VRAM. There is no
separate "1M" GGUF to download — native context is 262,144 and 1M is reached
with runtime YaRN flags. Nothing needed installing.

At 1M it needs **q4_0 KV** — q8_0 KV is 13,056 MiB and the ~1.9 GB compute
buffer pushes it past 16,304 MiB. Measured failure, not an estimate.

---

## Verified server configs

Every row below was **actually loaded on the ROCm build** and confirmed to
reach `server is listening`, with the VRAM figure read from
`/sys/class/drm/card1/device/mem_info_vram_used` while resident. All include
`-ngl 99`. Contexts are exact token counts, not rounded labels.

### Qwen3.6-35B-A3B — 20.6GB, MoE 35B/~3B active, general

| Context | Extra flags | VRAM used | Free |
|---|---|---|---|
| 4K | `-ncmoe 16 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,635 | 1,669 |
| 32K | `-ncmoe 16 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,932 | 1,372 |
| 128K | `-ncmoe 20 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,090 | 2,214 |
| 256K | `-ncmoe 24 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,471 | 1,833 |
| 512K | `-ncmoe 32 -ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 13,338 | 2,966 |
| 1M | `-ncmoe 40 -ub 256 -b 1024 -fa on -ctk q8_0 -ctv q8_0` | 15,480 | 824 |

### Qwen3-Coder-Next — 49.3GB, MoE 80B/~3B active, coding specialist

| Context | Extra flags | VRAM used | Free |
|---|---|---|---|
| 32K | `-ncmoe 38 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 13,444 | 2,860 |
| 128K | `-ncmoe 40 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 13,181 | 3,123 |
| 256K | `-ncmoe 42 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 13,894 | 2,410 |
| 1M | `-ncmoe 46 -ub 256 -b 1024 -fa on -ctk q4_0 -ctv q4_0` | 13,874 | 2,430 |

Host RAM at these settings is ~47GB (the 46,767 MiB CPU-mapped model buffer),
so this model wants the machine otherwise idle.

### GPT-OSS-20B — 11.3GB, MoE 21B/~3.6B active

Vulkan-era `-ncmoe` values re-verified as still loading on ROCm, unchanged:

| Context | Extra flags | VRAM used | Free |
|---|---|---|---|
| 128K | *(none)* | 15,326 | 978 |
| 256K | `-fa on -ctk q8_0 -ctv q8_0` | 15,917 | 387 |
| 512K | `-ncmoe 9 -fa on -ctk q8_0 -ctv q8_0` | 16,028 | 276 |
| 1M | `-ncmoe 24 -fa on -ctk q4_0 -ctv q4_0` | 11,632 | 4,672 |

### Gemma 4-26B-A4B — 15.8GB, MoE 25.2B/~3.8B active, 30 layers

**Re-tuned — the old Vulkan values do not load on ROCm.** `-ncmoe 8` @128K and
`-ncmoe 16` @256K both fail to allocate. ROCm needs roughly double:

| Context | Old (Vulkan) | New (ROCm) | VRAM used | Free |
|---|---|---|---|---|
| 4K | `-ncmoe 3` | `-ncmoe 6` | 14,688 | 1,616 |
| 32K | `-ncmoe 5` | `-ncmoe 8` | 14,338 | 1,966 |
| 128K | `-ncmoe 8` ✗ | `-ncmoe 12` | 14,437 | 1,867 |
| 256K | `-ncmoe 16` ✗ | `-ncmoe 20` | 13,811 | 2,493 |

Gemma 4 hard-caps at 256K. It is *not* a hybrid-attention model, which is why
its VRAM scales so much worse with context than the two Qwen models.

---

## Throughput

`llama-bench`, `-r 2`, ROCm build, shallow depth unless noted.

### Qwen3.6-35B-A3B — `-ub 1024`, q8_0 KV, pp4096/tg64

| `-ncmoe` | Prompt tok/s | Gen tok/s |
|---|---|---|
| 40 | 1198.0 | 31.8 |
| 36 | 1268.4 | 33.4 |
| 32 | 1368.0 | 35.7 |
| 28 | 1472.6 | 35.8 |
| 24 | 1616.2 | 39.0 |
| 20 | 1787.3 | 41.9 |
| 16 | 1974.8 | 43.9 |

Monotonic — every expert layer moved onto the GPU helps. `-ncmoe 12` fails to
allocate even at minimal context, so 16 is the floor. The usable value is
whatever the target context leaves room for (see the config table).

### Qwen3-Coder-Next — pp2048/tg64

| `-ncmoe` | `-ub` | KV | Prompt tok/s | Gen tok/s |
|---|---|---|---|---|
| 38 | 1024 | q8_0 | 722.4 | 25.0 |
| 40 | 1024 | q8_0 | 697.3 | 25.8 |
| 42 | 1024 | q8_0 | 680.6 | 25.1 |
| 44 | 256 | q4_0 | 246.6 | 24.4 |
| 46 | 256 | q4_0 | 235.7 | 23.8 |
| 48 | 256 | q4_0 | 225.8 | 21.7 |

The `-ub 256` rows are the 1M-capable configs — note prompt throughput is ~3x
lower there. 1M costs a lot of prompt speed on this model.

### Generation decay with depth — Qwen3.6, `-ncmoe 40 -ub 1024`

| Depth | Gen tok/s |
|---|---|
| 0 | 31.8 |
| 32K | 28.8 |
| 131K | 22.2 |

---

## Tuning findings

**`-ub` (ubatch) is the most under-used flag.** Qwen3.6, `-ncmoe 40`, pp4096:

| `-ub` | Prompt tok/s |
|---|---|
| 256 | 416.1 |
| 512 *(default)* | 706.0 |
| 1024 | 1198.0 |

**+70% over the default** for larger VRAM cost. Raise it whenever the context
budget allows; drop to 256 only when squeezing in 1M.

**KV cache type — match them, never mix.** Qwen3.6, `-ncmoe 36`, pp512/tg128:

| `-ctk` / `-ctv` | Prompt tok/s | Gen tok/s |
|---|---|---|
| q8_0 / q8_0 | 776.7 | 33.4 |
| f16 / f16 | 753.0 | 34.8 |
| f16 / q8_0 | 600.9 | 33.2 |
| q8_0 / f16 | 603.6 | 33.0 |

Mixed precision costs ~23% prompt throughput for no memory benefit. q8_0/q8_0
is the right default: same speed as f16, half the memory.

**Threads — leave at 16, never 32.** Qwen3.6, `-ncmoe 36`, pp512/tg128:

| `-t` | Prompt tok/s | Gen tok/s |
|---|---|---|
| 8 | 750.3 | 34.7 |
| 16 *(default)* | 756.7 | 34.0 |
| 24 | 774.3 | 33.0 |
| 32 | 775.2 | **23.6 ± 4.6** |

`-t 32` collapses generation with high variance — SMT contention across all
32 threads. 8/16/24 are within noise of each other.

**`--no-kv-offload` is a trap.** It frees a lot of VRAM (1M Coder-Next drops
from ~15.5GB to 6.1GB) but moves KV to system RAM over PCIe. Qwen3.6, tg64:

| Depth | KV in VRAM | KV in RAM (`-nkvo`) |
|---|---|---|
| 32K | 28.8 | 14.7 |
| 131K | 22.2 | 7.7 |

Halved at 32K, ~3x worse at 131K. Reduce context or KV quant instead.

**Watch for other GPU consumers.** DaVinci Resolve holds ~10.4 GB of VRAM
while open, which silently forces far more conservative `-ncmoe` values. If a
previously-working config suddenly fails to allocate, check for it before
re-tuning. Idle `ollama serve` holds nothing.

**YaRN caveat.** Beyond each model's native 262,144, `--rope-scaling yarn
--rope-scale 4 --yarn-orig-ctx 262144` is required for quality. Note that
`print_info: rope scaling = linear` in the log reflects **GGUF metadata, not
the runtime flag**, so it is not a reliable confirmation that YaRN engaged —
verify with a retrieval test at depth if it matters for your use.

---

## Commands

Persistent server (OpenAI-compatible API, reachable on the LAN) — note the
`build/` path:

```bash
nohup ~/llama.cpp/build/bin/llama-server -m models/<file>.gguf -ngl 99 [-ncmoe N] \
  [-ub 1024 -b 2048] [-fa on -ctk q8_0 -ctv q8_0] -c <context> -np 1 \
  --host 0.0.0.0 --port 8090 > /tmp/llama-server.log 2>&1 < /dev/null &
disown
```

```bash
curl -s http://192.168.4.228:8090/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"<name>","messages":[{"role":"user","content":"<prompt>"}],"max_tokens":300}'
```

Recommended sampling for Qwen3-Coder-Next: `temp 1.0`, `top_p 0.95`,
`top_k 40`, `min_p 0.01`, repeat penalty disabled.

### Reading GGUF metadata

Attention topology decides long-context viability, so check it before
downloading anything large:

```bash
~/llama.cpp/build/bin/llama-server -m models/<file>.gguf -c 512 --no-warmup 2>&1 | grep -iE "block_count|full_attention_interval|head_count_kv|key_length|context_length"
```

## How to switch models

```bash
~/llama.cpp/switch-model.sh <model> <context>   # gpt-oss-20b|qwen3.6|gemma4|qwen3-coder
~/llama.cpp/switch-model.sh status              # what's running now
~/llama.cpp/switch-model.sh list                # verified combinations
```

There is no hot-swap — one `llama-server` process holds one model, and clients
cannot switch it by changing the `"model"` field in a request.

---

## Model inventory

| Model | Total | Active | Type | Quant | Size | On disk |
|---|---|---|---|---|---|---|
| GPT-OSS-20B | 21B | ~3.6B | MoE | MXFP4 | 11.3GB | yes |
| Qwen3.6-35B-A3B | 35B | ~3B | MoE hybrid, 40L | UD-Q4_K_M | 20.6GB | yes |
| Gemma 4-26B-A4B | 25.2B | ~3.8B | MoE, 30L | UD-Q4_K_M | 15.8GB | yes |
| Qwen3-Coder-Next | 80B | ~3B | MoE hybrid, 48L | UD-Q4_K_M | 49.3GB | yes |
| Qwen2.5-Coder-14B | 14B | 14B | Dense | Q4_K_M / Q8_0 | 8.4 / 14.6GB | deleted |
| Qwen2.5-Coder-32B | 32B | 32B | Dense | Q4_K_M | ~19GB | deleted |
| GPT-OSS-120B | 117B | ~5.1B | MoE | MXFP4 | 59.0GB | deleted |

---

## Superseded: Vulkan-backend numbers

Kept only for historical comparison. **Do not use these configs** — the ROCm
tables above replace them. Measured with `build-vulkan/`, and via a different
method (`llama-cli` at the stated context) than the `llama-bench` figures
above, so the two are not directly comparable.

| Model | Context | Config | VRAM | Prompt tok/s | Gen tok/s |
|---|---|---|---|---|---|
| GPT-OSS-20B | 4K | `-ngl 99` | 11,918 | 1078.8 | 173.4 |
| GPT-OSS-20B | 32K | `-ngl 99` | 12,591 | 818.9 | 180.5 |
| GPT-OSS-20B | 128K | `-ngl 99` | 14,900 | 979.4 | 181.0 |
| GPT-OSS-20B | 256K | `-fa on -ctk q8_0 -ctv q8_0` | 15,464 | 961.0 | 171.1 |
| GPT-OSS-20B | 512K | `-ncmoe 9 -fa on -ctk q8_0 -ctv q8_0` | 15,863 | 150.0 | 44.9 |
| GPT-OSS-20B | 1M | `-ncmoe 24 -fa on -ctk q4_0 -ctv q4_0` | 11,338 | 71.8 | 24.1 |
| GPT-OSS-120B | 4K | `-ncmoe 28` | 15,789 | 26.9 | 19.8 |
| GPT-OSS-120B | 32K | `-ncmoe 29` | 15,253 | 26.5 | 19.4 |
| GPT-OSS-120B | 128K | `-ncmoe 31` | 15,738 | 24.7 | 18.7 |
| Qwen3.6-35B-A3B | 4K | `-ncmoe 12` | 16,156 | 131.1 | 48.1 |
| Qwen3.6-35B-A3B | 32K | `-ncmoe 14` | 15,817 | 126.4 | 45.9 |
| Qwen3.6-35B-A3B | 128K | `-ncmoe 18` | 15,879 | 115.1 | 41.2 |
| Qwen3.6-35B-A3B | 256K | `-ncmoe 18 -fa on -ctk q8_0 -ctv q8_0` | 16,003 | 83.8 | 30.6 |
| Qwen3.6-35B-A3B | 512K | `-ncmoe 25 -fa on -ctk q8_0 -ctv q8_0` | 16,092 | 94.0 | 34.8 |
| Qwen3.6-35B-A3B | 1M | `-ncmoe 42 -fa on -ctk q8_0 -ctv q8_0` | 16,111 | 75.3 | 28.8 |
| Qwen3-Coder-Next | 4K | `-ncmoe 35` | 15,273 | 62.6 | 26.4 |
| Qwen3-Coder-Next | 32K | `-ncmoe 35` | 15,999 | 64.0 | 26.4 |
| Gemma 4-26B-A4B | 4K | `-ncmoe 3` | 15,689 | 256.4 | 69.2 |
| Gemma 4-26B-A4B | 32K | `-ncmoe 5` | 15,813 | 208.2 | 53.6 |
| Gemma 4-26B-A4B | 128K | `-ncmoe 8` | 15,924 | 139.2 | 43.7 |
| Gemma 4-26B-A4B | 256K | `-ncmoe 16` | 15,748 | 122.6 | 35.1 |

Note on the old Qwen3.6 1M row: `-ncmoe 42` exceeds the model's 40 layers and
silently clamps to 40, i.e. all experts on CPU. Values ≥ the layer count are
the slowest possible setting.
