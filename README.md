# Local LLM Benchmarks — CachyPC

## Hardware

Every number in this file was measured on this machine. The right-hand column
is why each spec keeps showing up in the results.

| Component | Spec | Why it matters here |
|---|---|---|
| **GPU** | AMD Radeon RX 9070 XT — Navi 48, `gfx1201`, RDNA4, **16,304 MiB VRAM** | The binding constraint on this whole file. Every `-ncmoe`, KV-quant and `-ub` decision is bought against these 16GB |
| **CPU** | AMD Ryzen 9 5950X — 16C/32T, 64 MiB L3, 5.09 GHz boost | Runs CPU-offloaded expert layers. `-t 32` collapses generation to 23.6 ± 4.6 tok/s on SMT contention; leave threads at 16 |
| **RAM** | 64 GB DDR4-3200 — 4 × 16 GB, dual channel, all four slots filled | Feeds CPU-offloaded expert layers at ~40 GB/s, which is the real ceiling on every `-ncmoe` row. Qwen3-Coder-Next also holds ~47 GB resident, so that model wants the box otherwise idle |
| **Storage** | Crucial BX500 1 TB — **SATA** SSD (~540 MB/s) | Not NVMe. This is why cold loads cost what they do: ~93s for the 49 GB Qwen3-Coder-Next, ~30s for a 12.5 GB model. Idle-sleep reloads pay it again |
| **OS** | CachyOS, kernel 7.1.5 | |
| **ROCm** | 7.2.53211 (`build/`, `GGML_HIP=ON`, `AMDGPU_TARGETS=gfx1201`) | Wins K-quants by 1.7-2.1x prompt |
| **Vulkan** | RADV, Mesa 26.1.6 (`build-vulkan/`) | Wins MXFP4 generation at shallow depth only |
| **llama.cpp** | `b10364` (`153d324bc`, 2026-08-11) | Tool calling was broken on `e583f3b4f` and fixed here — see the tool-calling section |

The GPU is `card1` on this box, so VRAM is read from
`/sys/class/drm/card1/device/mem_info_vram_used` throughout.

**The memory config is worth stating, because `-ncmoe` rows are partly a DDR4
benchmark.** The four DIMMs are two different kits, interleaved one per channel
rather than one kit per channel:

| Slot | Module | Rated | Running |
|---|---|---|---|
| A1, B1 | G.Skill `F4-3200C16-16GVK` | 3200 CL16 | 3200 |
| A2, B2 | Corsair `CMW32GX4M2D3600C18` | **3600** CL18 | 3200 |

The Corsair half is downclocked to the G.Skill's SPD speed. That is not
obviously performance left on the table: four mostly dual-rank DIMMs is
already the hardest case for a Zen 3 memory controller, and 3200 with all
slots filled is a reasonable landing point. But anything that moves host
memory bandwidth moves every CPU-offloaded number in this file, so it belongs
in the record. (`dmidecode` also reports B1 as single-rank while A1, the same
part number, reports dual — possibly an SPD reporting quirk, untested either
way.)

**Backend depends on the quant format — there is no single best build.**
`~/llama.cpp/switch-model.sh` picks the right one per model automatically.
Both builds exist: `build/` is `GGML_HIP=ON` (`AMDGPU_TARGETS=gfx1201`),
`build-vulkan/` is RADV.

---

## Headline: pick the backend by quant format

Measured head-to-head, `llama-bench`, **`-fa 1`** throughout (`llama-bench`
defaults flash attention *off*, but `llama-server` resolves `auto → enabled`,
so `-fa 0` numbers do not reflect real serving — an earlier revision of this
file got that wrong):

| Model | Quant | ROCm pp / tg | Vulkan pp / tg | Use |
|---|---|---|---|---|
| Qwen3.6-35B-A3B (`-ncmoe 40 -ub 512`) | Q4_K_M | **706.0** / — | 333.4 / 29.3 | ROCm |
| Gemma 4-26B-A4B (`-ncmoe 8`) | Q4_K_M | **1949.9** / **50.3** | 1064.7 / 48.0 | ROCm |
| GPT-OSS-20B, shallow | MXFP4 | **5529.9** / 148.5 | 4952.0 / **180.8** | Vulkan |
| GPT-OSS-20B, @131k depth | MXFP4 | **1035.2** / **70.5** | 1063.7 / 22.3 | **ROCm** |

**K-quants (Q4_K_M) → ROCm**, unambiguously: 1.8-2.1x prompt, and it wins
generation too once flash attention is on (Gemma 50.3 vs 48.0).

**MXFP4 (GPT-OSS) → depends on depth.** Shallow, Vulkan wins generation by 22%
(180.8 vs 148.5) while ROCm wins prompt by 12%. The two cross over at roughly
**57 prompt tokens per generated token** — below that ratio Vulkan is faster
overall, above it ROCm is.

At depth the picture changes completely: **Vulkan's generation collapses to
22.3 tok/s at 131k** while ROCm holds 70.5 at the same prompt speed. That is
VRAM pressure — 11.3GB model + 3GB f16 KV + compute against a 16,304 MiB card.
Quantising KV to q8_0 rescues Vulkan (99.9 tok/s) but halves its prompt speed
to 532. ROCm with f16 KV is the best 128k configuration overall, so
`switch-model.sh` routes `gpt-oss-20b:128k` to ROCm while leaving 32k on Vulkan.

Combining the ROCm switch with `-ncmoe`/`-ub` tuning gives **4.8x prompt /
+33% generation** over the old Qwen3.6 config (333.4/29.3 → 1616.2/39.0) — but
note the generation share of that comes from `-ncmoe 40 → 24`, not the backend.

**All Vulkan numbers at the bottom of this file are superseded.**

---

## Why 1M context is possible at all: hybrid attention

Qwen3.6-35B-A3B (`qwen35moe`), Qwen3-Coder-Next (`qwen3next`) and Qwen3.8-27B
(`qwen35`) are **hybrid attention** models. `full_attention_interval = 4` means
only every 4th layer keeps a KV cache; the rest are SSM/gated-linear layers
with a **constant-size recurrent state** that does not grow with context.

| Model | Layers | Layers with KV | KV heads | SSM state | KV @1M (q8_0) |
|---|---|---|---|---|---|
| Qwen3.6-35B-A3B | 40 | 10 | 2 | 62.81 MiB | 10,880 MiB |
| Qwen3-Coder-Next | 48 | 12 | 2 | 75.38 MiB | 13,056 MiB |
| Qwen3.8-27B | 64 | 16 | **4** | — | **34,816 MiB** |
| **Nemotron-3-Nano-30B-A3B** | 52 | **6** | 2 | — | **3,264 MiB** |

The first two use 2 KV heads × 256 key/value length — tiny per-layer KV on top
of the 1-in-4 layer count.

**Qwen3.8-27B is the counter-example, and it matters.** Same
`full_attention_interval = 4`, but 4 KV heads instead of 2 and 64 layers
instead of 40-48, so 16 layers keep KV at double the per-layer cost:
**34,816 bytes/token**, 2.7x Qwen3-Coder-Next. Confirmed exactly, not
estimated — asking for 131,072 tokens of q8_0 KV fails with `failed to
allocate ROCm0 buffer of size 4563402752`, which is 4,352 MiB, precisely
16 × 4 × 256 × 2 × 1.0625 × 131072.

So "hybrid attention" is not by itself a promise of cheap long context. Read
`head_count_kv` and `block_count` alongside `full_attention_interval` — the
interval tells you what fraction of layers cache, the other two tell you what
each of those layers costs.

**This is the whole reason 1M fits in 16GB.** A conventional full-attention
coder such as Qwen3-Coder-30B-A3B has KV on all 48 layers with 4 KV heads ×
128 dim ≈ 52 KB/token → **~52 GB of KV at 1M**. Not runnable here at any
quant. When shopping for long-context models on this box, check
`full_attention_interval` in the GGUF metadata first; parameter count matters
far less than attention topology.

### Native context limits — and why the presets stop there

From GGUF metadata:

| Model | Native context | Note |
|---|---|---|
| GPT-OSS-20B | **131,072** | already YaRN 32x from a 4,096 base |
| Qwen3.6-35B-A3B | 262,144 | |
| Gemma 4-26B-A4B | 262,144 | |
| Qwen3-Coder-Next | 262,144 | |
| Muse Glimmer 30B | 131,072 | dense, but 2 KV heads + sliding window |
| Qwen3.8-27B | 262,144 | **VRAM-capped at 131,072 here** — 256K does not fit |
| Nemotron-3-Nano-30B-A3B | **1,048,576** | reached natively here — no YaRN |
| Devstral Small 2 24B | 393,216 | **VRAM-capped at 32,768 here** — full attention on 40 layers |

`switch-model.sh` exposes **only contexts within these ranges** (32k/128k/256k).
Anything beyond needs YaRN RoPE scaling, which trades short-context quality for
reach — fine as a deliberate experiment, wrong as a preset you might pick by
accident. GPT-OSS-20B is the sharpest case: its 128K is *already* a 32x YaRN
stretch, so pushing further stacks a second extension on top.

### If you do want 1M

It works, and the configs below are measured, but you have to opt in by hand.
**Qwen3-Coder-Next is the only sensible choice** — it is the only
coding-specialist model whose hybrid architecture makes 1M viable in 16GB. A
conventional full-attention coder needs ~52GB of KV at 1M. There is no separate
"1M" GGUF to download; 1M is a runtime flag on the 262,144-native weights.

```bash
~/llama.cpp/build/bin/llama-server -m models/Qwen3-Coder-Next-UD-Q4_K_M.gguf \
  -ngl 99 -ncmoe 46 -ub 256 -b 1024 -fa on -ctk q4_0 -ctv q4_0 -c 1048576 \
  --rope-scaling yarn --rope-scale 4 --yarn-orig-ctx 262144 \
  -np 1 --host 0.0.0.0 --port 8090
```

Verified: 13,874 / 16,304 MiB, ~93s cold load. It requires **q4_0 KV** — q8_0
is 13,056 MiB and the ~1.9GB compute buffer then overflows the card (measured
failure, not an estimate). Prompt processing drops to ~236 tok/s because the
fit forces `-ub 256`; generation is barely affected (23.8 vs 25.8).

---

## Verified server configs

Every row below was **actually loaded on the backend named in its section
heading** and confirmed to reach `server is listening`, with the VRAM figure
read from
`/sys/class/drm/card1/device/mem_info_vram_used` while resident. All include
`-ngl 99`. Contexts are exact token counts, not rounded labels.

### Qwen3.6-35B-A3B — 20.6GB, MoE 35B/~3B active, general

| Context | Extra flags | VRAM used | Free |
|---|---|---|---|
| 32K | `-ncmoe 16 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,932 | 1,372 |
| 128K | `-ncmoe 20 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,090 | 2,214 |
| 256K | `-ncmoe 24 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,471 | 1,833 |
| *512K †* | `-ncmoe 32 -ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 13,338 | 2,966 |
| *1M †* | `-ncmoe 40 -ub 256 -b 1024 -fa on -ctk q8_0 -ctv q8_0` | 15,480 | 824 |

† Beyond native 262,144 — needs YaRN, not a `switch-model.sh` preset.

### Qwen3-Coder-Next — 49.3GB, MoE 80B/~3B active, coding specialist

| Context | Extra flags | VRAM used | Free |
|---|---|---|---|
| 32K | `-ncmoe 38 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 13,444 | 2,860 |
| 128K | `-ncmoe 40 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 13,181 | 3,123 |
| 256K | `-ncmoe 42 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 13,894 | 2,410 |
| *1M †* | `-ncmoe 46 -ub 256 -b 1024 -fa on -ctk q4_0 -ctv q4_0` | 13,874 | 2,430 |

† Beyond native 262,144 — needs YaRN, not a `switch-model.sh` preset.

Host RAM at these settings is ~47GB (the 46,767 MiB CPU-mapped model buffer),
so this model wants the machine otherwise idle.

### GPT-OSS-20B — 11.3GB, MoE 21B/~3.6B active — **backend varies by context**

32K on Vulkan (180.7 tok/s generation), 128K on ROCm (Vulkan's generation
collapses to 22.3 there — see the throughput section). Configs verified on both
backends. Half its layers use a 768-token sliding window, which is why 128K
costs only ~3GB of KV:

| Context | Extra flags | VRAM used | Free |
|---|---|---|---|
| 32K | *(none)* | — | — |
| 128K | *(none)* | 15,326 | 978 |
| *256K †* | `-fa on -ctk q8_0 -ctv q8_0` | 15,917 | 387 |
| *512K †* | `-ncmoe 9 -fa on -ctk q8_0 -ctv q8_0` | 16,028 | 276 |
| *1M †* | `-ncmoe 24 -fa on -ctk q4_0 -ctv q4_0` | 11,632 | 4,672 |

† Beyond native **131,072**, which is itself already a 32x YaRN stretch from a
4,096 base. These load and produce tokens, but stack a second extension on an
already-extended model — the least trustworthy rows in this file.

### Gemma 4-26B-A4B — 15.8GB, MoE 25.2B/~3.8B active, 30 layers

**Re-tuned — the old Vulkan values do not load on ROCm.** `-ncmoe 8` @128K and
`-ncmoe 16` @256K both fail to allocate. ROCm needs roughly double:

| Context | Old (Vulkan) | New (ROCm) | VRAM used | Free |
|---|---|---|---|---|
| 32K | `-ncmoe 5` | `-ncmoe 8` | 14,338 | 1,966 |
| 128K | `-ncmoe 8` ✗ | `-ncmoe 12` | 14,437 | 1,867 |
| 256K | `-ncmoe 16` ✗ | `-ncmoe 20` | 13,811 | 2,493 |

Gemma 4 hard-caps at 256K. It is *not* a hybrid-attention model, which is why
its VRAM scales so much worse with context than the two Qwen models.

### Muse Glimmer 30B — 12.4GB, **dense** 30B, 52 layers

The only dense model in the set, and the first one where `-ncmoe` is irrelevant —
every layer goes to the GPU or none does. It fits anyway because of its attention
layout: **2 KV heads against 32 query heads (16:1 GQA)**, and a 2048-token sliding
window on 3 of every 4 layers. Only 13 layers keep a full KV cache, so 128K costs
under a gigabyte.

| Context | Config | VRAM used | Free | Gen tok/s | Draft acceptance |
|---|---|---|---|---|---|
| 32K | DFlash, `-ub 512` | 15,422 | 882 | **52.4** | 70.9%, mean run 3.13 |
| 64K | DFlash, `-ub 256` | 15,374 | 930 | 50.5 | 67.7%, mean run 3.03 |
| 128K | no DFlash | 14,462 | 1,842 | 31.9 | — |

**Confirmed on the serving path**, not just in a bench: a `muse-glimmer-64k`
turn in Open WebUI reported `draft_n 1263` against `draft_n_accepted 810` —
**64.1% acceptance** at 12,573 depth, against the 67.7% measured for this
preset. Generation was 47.6 tok/s there versus the documented 50.5. Both sit
just under the bench figures, which is what a real workload at depth should
look like.

**DFlash is worth 1.64x.** It is a real 1.5GB drafter sidecar (5 blocks,
`block_size 16`), not a generic draft model — llama.cpp has first-class support
via `--spec-type draft-dflash` alongside `-md`. It costs ~0.9GB, which is why it
is dropped at 128K: with it VRAM sits at 16,255 of 16,304 MiB — 49 MiB free — and
any real prompt OOMs.

**`reasoning_strength` defaults to `high` and will eat your entire token budget
before writing a single character of content.** It is a Jinja variable in the
chat template, *not* a system-prompt string — putting "Reasoning: low" in a
system message does nothing at all. Only `--chat-template-kwargs` sets it:

| Setting | Reasoning output | Result |
|---|---|---|
| `high` (default) | 1,611 chars | truncated at the cap, no code |
| `low` | 428 chars | `finish: stop`, complete answer |

llama.cpp splits it into `reasoning_content`, so `content` stays clean for
API clients either way — the problem is purely that reasoning consumes the
`max_tokens` budget.

Its tool-call format is `<atem:function_calls>` / `<atem:invoke>` XML with
`<|start|>assistant to=self<|message|>` channels — neither Qwen's nor Gemma's
shape. Whether llama.cpp's parser handles it under a native-tool-call harness
is **untested**; Cline bypasses the question by using prompt-based XML tools.

### Qwen3.8-27B — 12.5GB, **dense** 27B, 64 layers, hybrid attention, thinking

Arch is `qwen35`, so build `153d324bc` already serves it — no rebuild, and
upstream has no Qwen3.8-specific commits to pull. It is the first model here
that is dense *and* hybrid-attention, and the combination is unkind: no
`-ncmoe` to trade, and 34,816 B/token of KV.

| Context | Extra flags | VRAM used | Free |
|---|---|---|---|
| 32K | `-ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,610 | 1,694 |
| 64K | `-ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 15,543 | 761 |
| 128K | `-ub 256 -b 2048 -fa on -ctk q4_0 -ctv q4_0` | 16,023 | **281** |

**64K deliberately runs q8_0 at the tighter fit.** The obvious choice is q4_0
`-ub 1024`, which loads at 14,801 with a comfortable 1,503 MiB free — and that
is what this preset shipped as initially. It was wrong: q4_0 costs up to 23%
of generation at exactly the depths this preset exists for. Trading 742 MiB of
headroom for that back is the better deal. Verified under a 63,756-token
prompt: no OOM, 5/5 needle recall, ~600 tok/s cold prefill.

Rejected along the way, all measured:

| Attempt | Result |
|---|---|
| 128K, q8_0 KV | **fails to allocate** — wants 4,352 MiB of KV |
| 128K, q4_0, `-ub 1024` | loads at 16,247 — **57 MiB free** |
| 128K, q4_0, `-ub 512` | loads at 16,127 — 177 MiB free |
| 64K, q8_0, `-ub 1024` | loads at 15,811 — 493 MiB free, thinner than `-ub 512` for ~nothing |
| 64K, q4_0, `-ub 1024` | loads at 14,801 — roomy, but 23% slower at depth |
| 256K, any KV quant | 12,818 MiB weights + 4,608 MiB q4_0 KV > 16,304. Not attempted |

**The 281 MiB margin at 128K is real, not luck.** The obvious worry is the
Muse Glimmer + DFlash case, where 49 MiB free meant any real prompt OOMed. It
does not happen here, because the compute buffer is sized from `-ub` at load
time and does not grow with prompt length. Verified by pushing a
**127,116-token** prompt through the 128K preset: no OOM, and 5/5 needle
recall. What that margin does cost you is robustness against *other* GPU
consumers — 281 MiB is less than any browser compositor, let alone Resolve.

Two GGUF quirks worth knowing:

* `block_count` is **65**, not 64. `blk.64` is a Multi-Token-Prediction head
  (`nextn.eh_proj`, `nextn.shared_head_norm`, `nextn_predict_layers = 1`) and
  llama.cpp discards it — `model has unused tensor blk.64.* -- ignoring`.
  That is **198.8 MiB** of the file you store and never execute. It also means
  the model's own speculative-decoding mechanism is unavailable, unlike Muse
  Glimmer where DFlash is first-class and worth 1.64x.
* Unsloth's `UD-Q3_K_XL` reports internally as `Q4_K - Small` at 3.93 BPW.
  The name is the recipe, not the block type; do not match on it.

### Nemotron-3-Nano-30B-A3B — 22.8GB, MoE 31.6B/~3.5B active, Mamba2 hybrid

Arch is `nemotron_h_moe`; the build already had it, so no rebuild. **This is
the only model here whose 1M context is native.** 52 layers, of which just six
keep KV — indices 5, 12, 19, 26, 33, 42 — at 2 heads x 128. The rest are
Mamba-2 and MLP with constant-size recurrent state.

| Context | Extra flags | VRAM used | Free |
|---|---|---|---|
| 32K | `-ncmoe 24 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,747 | 1,557 |
| 128K | `-ncmoe 24 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 15,060 | 1,244 |
| 256K | `-ncmoe 24 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 15,723 | 581 |
| 512K | `-ncmoe 28 -ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,753 | 1,551 |
| **1M** | `-ncmoe 32 -ub 256 -b 1024 -fa on -ctk q4_0 -ctv q4_0` | **14,104** | **2,200** |

**None of these need YaRN.** Every previous 1M row in this file was a RoPE
stretch beyond a 262,144-trained range, flagged as the least trustworthy
configuration here. 1,048,576 is this model's trained context, so the
long-context rows carry the same status as its short ones.

Against the closest structural match already on the box, at identical `-ncmoe 24`:

| | Qwen3.6-35B-A3B | Nemotron-3-Nano-30B-A3B |
|---|---|---|
| Prompt, shallow | 1616.2 | **1912.8** (+18%) |
| Generation, shallow | 39.0 | **47.5** (+22%) |
| Generation @131K | 22.2 | **31.7** (+43%) |
| KV per token (q8_0) | 10,880 B | **3,264 B** |
| Native context | 262,144 | **1,048,576** |
| Host RAM | ~20 GB | ~22 GB |

I could not find an axis on which Qwen3.6 wins.

**What blocks 1M is the compute buffer, not the cache.** At `-ub 1024` it asks
for a 4,038 MiB compute buffer and fails even with heavy expert offload; the KV
itself is only 3,264 MiB. Dropping to `-ub 256` with q4_0 KV and `-ncmoe 32`
lands it with 2,200 MiB spare. Worth knowing because the instinct on an
allocation failure is to raise `-ncmoe`, which does nothing here.

512K at `-ncmoe 24 -ub 512` also "loads" — at 19 MiB free, where the very first
generation request failed. It is in the rejected pile, not the table; `-ncmoe
28` is the working value.

Same thinking trap as Qwen3.8: default reasoning returns **zero content** at
`max_tokens 1200`. `--reasoning-budget 1024` restores it (850 and 4,459 chars at
1200 and 2000 tokens). Its template uses `enable_thinking`, so `--no-think`
works on the probes; there is no `reasoning_effort`.

### Devstral Small 2 24B — 14.3GB, **dense** 24B coding specialist, Apache 2.0

Arch is `mistral3`, already in the build. It is the mirror image of Nemotron:
**full attention on all 40 layers** at 8 KV heads x 128, which is **87,040
B/token** at q8_0 — the most expensive KV in this file, 2.5x Qwen3.8 and 26x
Nemotron. Its native 393,216 is not remotely reachable; 128K alone would want
10,880 MiB of cache on top of 13,670 MiB of dense weights.

| Context | Extra flags | VRAM used | Free |
|---|---|---|---|
| 32K | `-ub 512 -b 2048 -fa on -ctk q4_0 -ctv q4_0` | 15,663 | 641 |

| Attempt | Result |
|---|---|
| 32K, q8_0 KV | **fails to allocate** — wants 2,720 MiB |
| 32K, q4_0, `-ub 1024` | loads at 15,914 — 390 MiB free |
| 16K, q8_0, `-ub 1024` | loads at 15,800 — 504 MiB free, *less* room than 32K at q4_0 |

That last row is why only one preset exists: **32K at q4_0 leaves more headroom
than 16K at q8_0**, so halving the window buys nothing.

**It is the fastest coder here, and the shallowest.** Fully GPU-resident, so no
`-ncmoe` and no host RAM pressure — 14.3GB against Qwen3-Coder-Next's 49.3GB
and ~47GB resident.

| Depth | Devstral Small 2 | Qwen3-Coder-Next |
|---|---|---|
| 0 | **36.0** tok/s / 1459 pp | ~25 / ~700 |
| 8K | 32.2 | — |
| 16K | 28.8 | — |
| 32K | 24.1 | ~24 |
| 47K | — | 22.6 |
| 256K | **unreachable** | ~22 |

44% faster shallow and roughly 2x on prompt, converging with Qwen3-Coder-Next
by 32K — which is also where it stops. A 33% generation decay across just 32K
is the steepest per-token in this file, and it is the 87,040 B/token doing it.

So the two coders are complements, not substitutes: **Devstral for short work,
Qwen3-Coder-Next for depth.**

`-ub` confirms the CPU-offload rule again: **+10.9%** from 256 to 1024
(1331.0 → 1475.8), against Qwen3.8's +11% and Qwen3.6's +188%. Two independent
fully-resident models now agree.

Not a thinking model — no `<think>` handling in its template, so unlike Qwen3.8
and Nemotron it needs no `--reasoning-budget`. The GGUF embeds no sampling
defaults.

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

### GPT-OSS-20B — Vulkan, `-fa 1`, depth sweep

| Depth | Prompt tok/s | Gen tok/s |
|---|---|---|
| 0 | 4921.1 | 180.7 |
| 32K | 2587.9 | 143.5 |
| 131K | 1063.7 | **22.3** ← VRAM cliff, use ROCm here |

At 131k on **ROCm** instead: 1035.2 prompt / **70.5** generation — same prompt
speed, 3.2x the generation. This is why `gpt-oss-20b:128k` is routed to ROCm.

Flash attention is worth having: on Vulkan at depth 0, `-fa 1` gives 4921/180.7
versus 3775/178.0 with `-fa 0` — **+30% prompt**. The presets pass no `-fa`
flag, which is fine: `llama-server` defaults to `auto` and resolves it to
enabled (`sched_reserve: Flash Attention was auto, set to enabled`).

GPT-OSS-20B is by far the fastest model here — fully GPU-resident at 11.3GB
with no `-ncmoe` at all, reading weights from VRAM at ~640 GB/s instead of
streaming from DDR4 at ~40 GB/s. Real-world: the same "write a Rust backend and
React frontend" prompt took **15s** on GPT-OSS-20B vs **1m55s** on
Qwen3-Coder-Next.

### Gemma 4-26B-A4B — ROCm, `-fa 1`, pp4096/tg64

| `-ncmoe` | Used at | Prompt tok/s | Gen tok/s |
|---|---|---|---|
| 8 | 32K | 1960.6 | 49.8 |
| 12 | 128K | 1603.6 | 42.6 |
| 20 | 256K | 1276.0 | 33.9 |

Depth sweep at `-ncmoe 8`, tg64 — **the flattest curve of any model here**:

| Depth | Gen tok/s |
|---|---|
| 0 | 51.4 |
| 8K | 49.0 |
| 16K | 47.5 |
| 32K | **47.0** |

**8.5% decay across the whole range**, against Qwen3.8's 14% at q8_0 and 34%
at q4_0, and Qwen3.6's 30% out to 131K. Gemma 4 is not a hybrid-attention
model and pays for that in VRAM, but what it buys is generation speed that
barely notices depth.

That makes it the answer to "fastest model that is still a serious 25B+ at
Q4_K_M": it never drops below 47 tok/s inside 32K, where Qwen3.8 at the same
depth is at 27.0 and a full quant step lower at Q3_K_XL.

### Qwen3.8-27B — ROCm, `-fa 1`, pp4096/tg64

Ubatch sweep at q8_0 KV, shallow:

| `-ub` | Prompt tok/s | Gen tok/s |
|---|---|---|
| 256 | 1180.7 | 31.9 |
| 512 | 1279.7 | 31.9 |
| 1024 | 1306.9 | 31.9 |

**`-ub` almost does not matter on this model — +11% across the whole range,**
against +188% on Qwen3.6. That is not a contradiction, it is the mechanism
showing itself: Qwen3.6 at `-ncmoe 40` streams expert weights from DDR4 every
batch, and a larger ubatch amortises that transfer. Qwen3.8 is dense and fully
GPU-resident, so there is no host traffic to amortise and ubatch only trades
compute-buffer size against a little scheduling overhead. The practical payoff
is that `-ub 256` — mandatory to fit 128K — costs about 10% here, where the
same drop costs Qwen3-Coder-Next roughly 3x.

Depth sweep, q4_0 KV, `-ub 256` (the 128K preset):

| Depth | Prompt tok/s | Gen tok/s |
|---|---|---|
| 0 | 1180.4 | 31.6 |
| 32K | 551.2 | 20.8 |
| 131K | 213.4 | **9.6** |

**Those generation figures are the worst case, not the model's.** They were
measured at q4_0 KV, which costs up to 23% at depth (see Tuning findings). The
32K preset runs q8_0 and is materially faster:

| Depth | Gen, q8_0 (32K preset) | Gen, q4_0 (128K preset) |
|---|---|---|
| 0 | 31.6 | 31.5 |
| 8K | 30.6 | 27.8 |
| 16K | 29.4 | 25.1 |
| 32K | **27.0** | 20.8 |

So Qwen3.8 holds above 30 tok/s to roughly **12K** of depth at q8_0, and is
still at 27.0 at 32K. An earlier revision of this file put that crossover near
5K, by reading the q4_0 curve and applying it to the q8_0 preset.

**This is the worst generation decay in the file: 3.3x.** Compare Qwen3.6 over
the same range, 31.8 → 22.2, only 1.43x. The cause is the same 4-KV-heads ×
16-layers arithmetic — every generated token reads the whole KV cache, and
here that cache is 2.7x fatter per token than any other hybrid model in the
set. At 131K this model generates slower than Qwen3-Coder-Next, an 80B.

So the honest reading of the 128K preset: it fits, it recalls perfectly, and
it is slow enough that you should reach for 32K or 64K unless you genuinely
need the window.

#### Real-world check: the same model under Open WebUI

Every number above is `llama-bench`. One serving datapoint from the actual
path — `qwen3.8-32k` via router mode, Open WebUI with web search enabled,
five sources pulled into the prompt:

| | Measured | `llama-bench` d0 | `llama-bench` d32K |
|---|---|---|---|
| Prompt | **798.4 tok/s** | 1306.9 | 551.2 |
| Generation | **27.8 tok/s** | 31.6 | 20.8 |

`prompt_n 15065`, `cache_n 11198`, `predicted_n 1071` — so this spans roughly
11K to 26K of depth, and both figures land between the d0 and d32K rows
exactly where the sweep predicts. The synthetic curve is not flattering
itself; it transfers.

Two incidental confirmations: `cache_n 11198` shows the prompt cache reusing
the prefix across turns, and 1,071 completion tokens with a fully written
answer is `--reasoning-budget 1024` doing its job — this is precisely the
shape of request that returned zero content before the cap.

**The 64K KV switch, measured the same way.** Same preset before and after the
q4_0 → q8_0 change, at comparable depth:

| 64K preset | Depth | Generation |
|---|---|---|
| q4_0, `-ub 1024` | 18,566 | 24.4 tok/s |
| q8_0, `-ub 512` | 17,052 | **29.1 tok/s** |

**+19.7%**, and `llama-bench` had predicted 29.39 at d16384 against 29.15
measured slightly deeper — within 0.8%. That is the second time the synthetic
curve has transferred to the serving path without flattering itself, which is
the reason to keep taking these readings rather than trusting `llama-bench`
alone.

**Caveat that bit immediately:** the turn totalled 28,701 tokens against a
32,768 window, 88% full, from five search results plus history. Search-
augmented chats fill 32K fast. Use `qwen3.8-64k` for those — it trades q8_0
KV for q4_0, which is a cheap price given the decay you are already paying at
that depth.

### Nemotron-3-Nano-30B-A3B — ROCm, `-fa 1`, `-ncmoe 24 -ub 1024`, q8_0 KV

| Depth | Prompt tok/s | Gen tok/s |
|---|---|---|
| 0 | 1912.8 | 47.5 |
| 32K | 1697.3 | 41.7 |
| 131K | 1225.6 | **31.7** |

**It still generates 31.7 tok/s at 131K** — the only model here above 30 at that
depth other than Gemma 4, and unlike Gemma 4 it can go to 1M. Decay from 0 to
131K is 33%, similar in shape to Qwen3.6's but starting 22% higher and ending
43% higher.

Recall at depth, `--no-think`: **5/5 needle at 127,569 tokens**, cached
follow-ups 1.1-1.2s against Qwen3.8's 2.6-3.3s at comparable depth.

#### The 1M preset costs prompt throughput, not generation

Measured on the serving path — `nemotron-1m` in Open WebUI with web search, at
10,717 depth (`cache_n 8236` + `prompt_n 2481`):

| | `nemotron-256k` (`-ncmoe 24 -ub 1024` q8_0) | `nemotron-1m` (`-ncmoe 32 -ub 256` q4_0) |
|---|---|---|
| Prompt | 1912.8 tok/s | **488.3 tok/s** |
| Generation | 41.7 @32K | **38.8 @10.7K** |

**Generation barely notices; prompt drops ~4x.** Two causes compound — `-ub 256`
instead of 1024, and eight more layers on the CPU — and both hit prefill rather
than decode. This is the same shape as Qwen3-Coder-Next at 1M (236 vs 697
prompt, 23.8 vs 25.8 generation), so it looks like a property of what a 1M
config has to give up on this card rather than anything model-specific.

**Practical consequence: `nemotron-1m` is not a daily driver.** At the ~10K
depths typical of a search-augmented chat, `nemotron-256k` gives roughly 4x the
prompt throughput at the same generation speed *and* better KV precision. Pick
the 1M preset only when the prompt genuinely exceeds 262,144 tokens.

Native tool calling also works through Open WebUI on this model — two
`search_web` calls with real result blocks in the same turn — and
`--reasoning-budget 1024` bounded the thinking ("Thought for 11 seconds")
rather than consuming the answer.

### Generation decay with depth — Qwen3.6, `-ncmoe 40 -ub 1024`

| Depth | Gen tok/s |
|---|---|
| 0 | 31.8 |
| 32K | 28.8 |
| 131K | 22.2 |

---

## Context quality: measured, not assumed

The common warning is that long-context recall degrades well before the nominal
window ("lost in the middle"). **On Qwen3-Coder-Next that does not happen
anywhere inside its native 262,144 range.** Tested two ways at four depths:

| Depth | Needle recall | Semantic recall | Cold prefill | Effective prefill | Cached follow-up |
|---|---|---|---|---|---|
| ~9.7K | 5/5 | 5/5 | 19.3s | 502 tok/s | 3.6s |
| ~38K | 5/5 | 5/5 | 68.8s | 552 tok/s | 4.7s |
| ~119K | 5/5 | 5/5 | 268.3s | 445 tok/s | 6.5s |
| ~241K | — | **5/5** | 749.0s | 322 tok/s | 8.3s |

Two probes, in this repo and copied to `~/llama.cpp/`:

- **`needle-test.py`** — plants distinct facts at 5/25/50/75/95% depth and asks
  for each. The easy case: verbatim fact, distinctive surface form, no
  competitors.
- **`semantic-recall-test.py`** — the hard case, and the one that matters for
  coding. Plants real helper functions among hundreds of similar utilities,
  then poses tasks describing what each helper *does* without ever naming it,
  with a deliberate near-miss distractor for each (`chunk_list` by count vs
  `chunk_by_weight` by weight; `parse_iso_date` vs `coerce_epoch_millis`).
  Each distractor sits *closer* to the question than its target, so proximity
  cannot be the cue. This is the "did it notice the helper already exists, or
  reimplement it" failure mode.

Both score 5/5 everywhere, including the 50% mid-context position. The model
retrieved on meaning and rejected every near-miss.

**Gemma 4-26B-A4B, thinking disabled via `--reasoning-budget 0`:** semantic
recall 5/5 at 23,251 tokens, with cached follow-ups at **0.5-0.8s** against
Qwen3.8's 2.5-3.2s at comparable depth. First run on this probe for anything
other than Qwen3-Coder-Next.

Note the mechanism: `--no-think` sends `enable_thinking: false`, which is a
Qwen chat-template variable and does nothing on Gemma 4. `--reasoning-budget 0`
is the model-agnostic way to force an immediate end of thinking, and is what
these numbers used.

**Qwen3.8-27B, spot-checked with `--no-think`:** needle 5/5 at 127,116 tokens
on the 128K preset (cold prefill 339.2s, ~375 tok/s; cached follow-ups
2.6-3.3s), and semantic recall 5/5 at 23,474 tokens. Not the full four-depth
sweep — enough to say that recall is not the reason to avoid its long-context
mode. Generation speed at that depth is (9.6 tok/s).

Both scripts take `--depth N` against any running server:

```bash
~/llama.cpp/semantic-recall-test.py --depth 200000
```

**Limits of this result:** single-hop (each task maps to exactly one helper),
clean signal (planted docstrings are accurate, unlike real code), and n=5 per
depth. This rules out a systematic collapse, not a subtle degradation. Nothing
here covers the beyond-native 512K/1M configs, where YaRN and (at 1M) q4_0 KV
both plausibly hurt — those remain untested.

### The real cost is prefill, not forgetting

**Prefill throughput nearly halves with depth** — 552 tok/s at 38K down to 322
at 241K — so cost grows superlinearly. 119K → 241K is 2.02x the tokens but
2.8x the time.

| | Cold | Warm (cached prefix) |
|---|---|---|
| 128K preset | ~4.5 min | ~6.5s |
| 256K preset | ~12.5 min | ~8.3s |

**Seen in the wild on Qwen3-Coder-Next:** a turn reporting `cache_n 46967`
against `prompt_n 14` — the entire 47K prefix reused, fourteen tokens new. The
3,825-token reply cost 169s of generation and essentially nothing in prefill,
where a cold 47K prompt would have added ~85s. That turn also gives the deepest
generation reading for this model, **22.6 tok/s at 46,981 depth**, against ~25
shallow: a 10% drop over a range where Qwen3.8 loses 34% and Nemotron 33%. The
"barely decays with depth" claim for this model is now measured, not asserted.

A 90x gap. At these depths the prompt cache is not an optimisation, it is the
entire viability of the mode. **Treat 256K as load-once-then-iterate**: dump a
subsystem in, then ask twenty questions against it. Any change to the prefix —
reordering files, editing the system prompt, inserting anything ahead of the
bulk source — costs the full cold prefill again.

If your workflow rebuilds the prompt every turn, 256K is unusable; use 32K or
128K, where a cache miss costs 20-270s instead of 750.

So keep context lean because rebuilding it is expensive, **not** because the
model forgets. If you can hold the prefix stable, there is no measured quality
reason to avoid the full window.

Practical ceiling: `143,777 tokens exceeds the available context size (131072)`
— usable input at the 128K preset is ~119K once you leave room for the reply.

## Thinking models: `reasoning_effort` does not bound anything

Muse Glimmer taught that a thinking model's default effort can eat the whole
token budget, and that `low` fixes it. **Qwen3.8-27B breaks the second half of
that lesson.** Its `reasoning_effort` defaults to `xhigh`, and the same
hard-prompt test gives:

| Setting | Reasoning chars | Content chars | finish |
|---|---|---|---|
| default (`xhigh`) | 4,684 | **0** | length |
| `xhigh` | 4,846 | **0** | length |
| `medium` | 2,574 | **0** | length |
| `low` | 2,533 | **0** | length |
| `enable_thinking=false` | 0 | 2,538 | length |

At `max_tokens: 1200`, **every** thinking setting returns zero content. `low`
halves the reasoning and still answers nothing. Raising the budget does not
converge either — it scales with whatever you give it:

| Setting | `max_tokens` | Reasoning chars | Content chars |
|---|---|---|---|
| `low` | 2,000 | 5,720 | 0 |
| `low` | 4,000 | 11,822 | 0 |
| default | 4,000 | 15,926 | 0 |
| `low` | 8,000 | 28,174 | 0 |

At 8,000 tokens there is still no `</think>` anywhere in the output, and the
trace reads `I'm truly stuck. Let me try a completely different approach` —
genuine non-termination, not a parser artifact.

**Fair caveat:** the prompt driving that table is a logic puzzle I wrote which
may be ill-posed, and models spin on unsolvable problems. On a well-posed hard
problem the default terminates normally (`stop` at 3,109 tokens). So the claim
is not "this model never stops thinking" — it is that **nothing in
`reasoning_effort` puts a ceiling on it**, so a bad prompt can consume any
budget you set.

The fix is llama.cpp's own flag, not a template kwarg:

| Config | Reasoning chars | Content chars |
|---|---|---|
| `--reasoning-budget 1024`, `max_tokens 1200` | 3,135 | **776** |
| `--reasoning-budget 1024`, `max_tokens 2000` | 4,298 | **3,584** |

`--reasoning-budget N>0` is supported in this build (`-1` unrestricted, `0`
immediate end, `N` a token cap), so every `qwen3.8` preset sets 1024. Note
this also retroactively validates the `reasoning-budget = 1024` already in the
Gemma 4 presets — it is a real cap, not an ignored value.

Two smaller notes:

* An invalid effort value **500s the request** rather than falling back — the
  chat template calls `raise_exception` and llama.cpp surfaces it as an
  internal error. `xhigh`/`medium`/`low` are the only accepted strings.
* One anecdote on whether the thinking is even buying accuracy: asked how many
  integers ≤ 1000 have exactly 6 divisors (answer 111), thinking mode said
  **110** and ran out of budget mid-explanation, while `enable_thinking=false`
  answered 111 and finished. n=1, so not a quality verdict — but it is not
  evidence for leaving thinking on either.

### The client's `max_tokens` is charged for reasoning too

`--reasoning-budget` bounds the thinking. It does **not** stop that thinking
from being billed against whatever `max_tokens` the client sends — and the
answer is written *after* the reasoning, so a cap that is comfortable for a
non-thinking model silently truncates a thinking one mid-sentence.

Seen in Open WebUI on `qwen3.8-128k`: a news summary stopped in the middle of
its final list item. Nothing in the server said so. `llama.cpp` logged a
completely ordinary completion —

```
release: id 0 | task 576 | stop processing: n_tokens = 13672, truncated = 0
```

`truncated = 0`, 13,672 tokens against a 131,072 window (10% full), no
`context full`, no `context shift`, and the reasoning budget never reached.
Every server-side explanation was ruled out by that one line. The cause was
Open WebUI's own `max_tokens`, in Controls → Advanced Params. Raising it fixed
it immediately.

**Rule of thumb: client `max_tokens` must exceed `reasoning-budget` plus the
answer you actually want.** With `--reasoning-budget 1024` and a typical
1,200-1,600 token answer, anything under ~2,500 will cut this model off. The
presets cannot enforce this — it is a client setting.

The tell is the token accounting. In the truncated response, Open WebUI
reported `output_tokens: 1095` against `completion_tokens: 653`; the ~440
token gap is reasoning, and content got only what was left. (Do not read that
gap as exactly the reasoning count — it varies more than the budget allows,
so Open WebUI appears to fold its follow-up-question and title generations
into `output_tokens` as well.)

### The probes needed a flag for this

`needle-test.py` sends `max_tokens: 60` and reads only `content`, so against
any thinking model it scores 0/5 regardless of actual recall — the reasoning
consumes the budget first. Both probes now take `--no-think`, which sends
`chat_template_kwargs: {"enable_thinking": false}`:

```bash
./needle-test.py --depth 119000 --no-think
./semantic-recall-test.py --depth 20000 --no-think
```

This also keeps the comparison fair: every long-context number already in this
file was measured on Qwen3-Coder-Next, which does not think at all.

## Output quality: the first measured difference between models

Everything above measures speed, VRAM and recall. None of it says whether a
model's answers are any *good*, and for a long time nothing here did. This is
one narrow case where the difference was unambiguous.

**The task:** an SVG/HTML bar chart with axis, labels and title, asked
conversationally in Open WebUI.

**Nemotron-3-Nano-30B-A3B produced a chart that renders blank.** It computed
bar geometry as `height="-45"`, anchoring `y` at the baseline and negating the
value, where a bar rising from a baseline needs `y = baseline - value` and a
positive height. A negative `width` or `height` on `<rect>` is invalid per the
SVG spec, so the element is silently not drawn — axis, ticks and labels all
render correctly and the bars simply are not there. No error anywhere.

The confounds were eliminated one at a time:

| Suspect | Ruled out by |
|---|---|
| Quantisation | it is `UD-Q4_K_XL`, not a Q3 like Qwen3.8 |
| Reasoning cap | identical at `--reasoning-budget` 1024 and 4096 |
| Sampling temperature | still wrong at `temp 0.25`, not just 1.0 |
| Unlucky sample | 4 regenerations, all four bars negative each time |

**Muse Glimmer 30B needed seven attempts** at the same chart, and only
succeeded after abandoning SVG for CSS `<div>` bars with percentage heights.

**Qwen3-Coder-Next got it right on a harder version of the same task** — ten
bars, a legend, rotated category labels and an axis title — three times over.
That is the control that makes this a comparison rather than an anecdote: same
box, same client, same quant family, and the *specialist* handled the strictly
harder chart while two generalists could not do the easy one.

| Model | Billed as | Result |
|---|---|---|
| Nemotron-3-Nano-30B-A3B | general reasoning | 0/4, negative heights |
| Muse Glimmer 30B | agentic specialist | 7 attempts, only via CSS bars |
| **Qwen3-Coder-Next** | **coding specialist** | **3/3 on a harder chart** |

**The failure is specific to SVG coordinate maths, not to charting.** Both
generalists produced correct scaffolding, labels, axes and colours, and both
fell over on geometry — mapping a value to a `y` origin and a positive height.
Muse Glimmer's chart worked the moment the bars became styled `<div>`s with
percentage heights, where the browser owns the layout. If you want a chart out
of a non-coding model, ask for CSS bars rather than SVG rects; it routes around
the part they get wrong.

**One honest caveat.** The failure reproduced reliably in a long chat carrying
web-search history, but did **not** reproduce in isolated single-turn API calls
— four neutral runs produced four correct charts. So the trigger appears to be
context-dependent rather than unconditional, and a fresh chat may behave better
than continuing a long search-heavy thread.

**Scope.** One task, one client, three models. This is not a coding benchmark and
Nemotron is not a coding model — it is a general reasoning model that happens
to be excellent at everything else measured in this file. Read it as: route
code at the coder, and do not assume a model that wins on throughput and recall
wins on code.

| Job | Model | Why |
|---|---|---|
| Code | `qwen3-coder` | correct geometry 3/3, verified tool calling, ~24 tok/s to 47K depth |
| Long context, general | `nemotron-256k` | 46 tok/s, native 256K, 5/5 recall |
| Beyond 262,144 | `nemotron-1m` | the only option that is natively trained there |
| Fast general | `gemma4` | 47 tok/s flat, Q4_K_M |

### Two different failure classes

A second task separates them further. Asked for the same chart **using
Recharts**, with no CDN URLs supplied, every model produced a blank page — but
for different reasons, and only one reason is the model's fault.

| Model | Scripts resolving | What broke |
|---|---|---|
| Qwen3-Coder-Next | 2/4 | invented `babel@7.23.0`; that package's last version is **6.23.0**, deprecated years ago |
| Devstral Small 2 | **3/4** | `Recharts.min.js` — no minified UMD exists in any version |

Both also omitted `prop-types`, which Recharts' UMD requires as a global
(`t.Recharts = e(t.React, t.PropTypes, t.ReactDOM)`).

**The React and Recharts code itself was correct in both cases** — right
`createRoot`, right `layout="vertical"` idiom for horizontal bars, right custom
tooltip signature, correctly sorted. They failed only on dependency URLs.

That is a **recall** failure, not a reasoning one, and it is the opposite of
the SVG case: no amount of thinking recovers a package version you never saw,
whereas pinning the URLs in the prompt fixes it completely. The geometry
failures above are not fixable that way.

Practical consequence: if you want a local model to use an unfamiliar library
from a CDN, **give it the exact script tags**. Verified working set:

```
https://unpkg.com/react@18/umd/react.production.min.js
https://unpkg.com/react-dom@18/umd/react-dom.production.min.js
https://unpkg.com/prop-types@15.8.1/prop-types.min.js
https://unpkg.com/recharts/umd/Recharts.js
https://unpkg.com/@babel/standalone@7/babel.min.js
```

`prop-types` must precede Recharts, and note Recharts ships **no** `.min` UMD —
adding one is the reasonable guess that both models made and that 404s.

A related failure worth keeping in mind: the same chart, rendered perfectly,
was titled "2024 Comparison" and ranked models two years stale — the web search
had surfaced old pages and the model anchored on them. Correct code, confidently
outdated content. It is the same shape as the fabrication cases below: nothing
malfunctions and the output is still wrong.

## Tool calling: verified, and previously broken by llama.cpp

Native tool calling — the OpenAI `tools` field, parsed by llama.cpp into
structured `tool_calls` — works on this hardware. This is worth stating
explicitly because for most of 2026-08-11 it did not, and the cause was not
the models.

### The probe

Prompt-based tool schemes (Cline, Open WebUI's "Default" function calling)
inject tool descriptions into the prompt and parse text back, so they succeed
even when the API path is broken. To test the real path, use **Native**
function calling and a tool whose output cannot be guessed:

```python
def get_probe_token(self, seed: int) -> str:
    """
    Return the secret probe token for a given seed. There is no way to
    derive this value without calling this function.
    :param seed: Integer seed for the token.
    """
    return f"PROBE-{random.Random(seed).randint(100000, 999999)}"
```

Expected: seed 42 → `PROBE-770487`, seed 7 → `PROBE-439563`, seed 1234 →
`PROBE-915965`. A model answering without calling cannot produce these.

### Results

| Model | Single call | Parallel calls | Notes |
|---|---|---|---|
| GPT-OSS-20B @128K | ✓ `PROBE-770487` | ✓ sum `1355528` | two calls in one turn, did the arithmetic itself |
| Qwen3-Coder-Next @128K | ✓ `PROBE-770487` | ✓ sum `1355528` | three calls — also delegated the addition to `add_numbers` |
| Muse Glimmer 30B @32K | ✓ | untested | via Open WebUI's own `write_note` tool |
| Qwen3.8-27B @32K | ✓ `PROBE-770487` | ✓ sum `1355528` | three calls — also delegated the addition to `add_numbers`; passes with thinking on *and* off |

Both models that were tested on the parallel case passed, but they solved it
differently: GPT-OSS made the two `get_probe_token` calls and added the results
in-head, while Qwen3-Coder made a third call to `add_numbers`. Both correct;
Qwen's is the behaviour you want in an agent loop, where reaching for the tool
beats trusting arithmetic done in the forward pass.

### The llama.cpp bug worth knowing about

On build `e583f3b4f` (2026-04-24), **every Qwen3-Coder-Next tool call 500'd**:

```
Failed to parse input at pos 22: <tool_call>
<function=Edit>
```

`pos 22` is exactly `len("<|im_start|>assistant\n")` — the parser consumed the
generation prompt and rejected the very first character the model produced. The
model was right: its GGUF chat template renders tool calls as
`'\n<tool_call>\n<function=' + name + '>\n'`, precisely what it emitted.

The cause is llama.cpp's `peg-native` format, which *derives* a grammar from
the model's chat template rather than using a hand-written parser (Gemma 4 is
one of the few with a dedicated `COMMON_CHAT_FORMAT_PEG_GEMMA4` mapper). The
derived grammar rejected valid output. Observed correlation: calls preceded by
prose parsed fine; a bare tool call at the start of a response did not.

**Fixed by 2026-08-11 (`153d324bc`).** Same model, same prompt, same harness
now returns the correct token.

Two lessons that generalise:

* A tool-calling failure is not evidence the model is bad at tool use. Check
  the server build before blaming the model — retrying cannot help, since the
  model regenerates the same valid-but-rejected shape.
* `--jinja` is **enabled by default** in current builds (`common.h`:
  `bool use_jinja = true`). Adding the flag is not a fix for anything.

### Code execution, and how silently it fails without it

Open WebUI's Code Interpreter must be enabled in **two** places: Admin Panel →
Settings → Code Execution, *and* the per-chat toggle in the `+` menu next to the
message box. With only the first done there is no error and no warning — the
model simply answers from nothing.

Same model (Qwen3-Coder-Next @128K), same three questions, twenty minutes apart:

| Question | No interpreter | With interpreter | Correct |
|---|---|---|---|
| sha256 of `nipuna-rx9070xt-muse-glimmer-2026-08-11` | `c4e1e9e7b2a8…` | `0f68974a8db2ab1b22a17ff82b4ac21198c38b22d8fa0a448caa69cf8f169043` | ✓ |
| primes below 987654 | 77,597 | **77,614** | ✓ |
| digit sum of 7^777 | 3,519 | **2,989** | ✓ |

With execution available it used it unprompted, on all three, and got every
answer right. Without it, it fabricated all three.

**Pick test values that cannot be memorised.** An earlier run of this test used
`sha256("hello world")`, the count of primes below 100000, and the 5000th prime
— and "passed" without executing anything, because all three are in training
data. The tell was formatting: the sum came back as `4,543,965,37`, comma-grouped
wrong, which is what recalled digits look like rather than a formatted integer.
The fabricated hash has a similar signature — its tail reads `a8b9c0d1e2f3a4b5`,
ascending hex pairs.

The prime count is the dangerous case. A wrong hash is obviously wrong; 77,597
against 77,614 passes a glance.

### llama.cpp parses tool calls even when none were offered

With no tools installed or enabled, the model emitted a call to
`calculate_timestamp` — a function that does not exist anywhere — and Open WebUI
rendered it as `View Result from calculate_timestamp` above a fabricated answer.

Nothing malfunctioned. Asked to compute something it could not, the model emitted
its native `<tool_call><function=…>` syntax for an invented tool; llama.cpp's
`peg-native` parser converts that to a structured `tool_calls` field regardless
of whether the client sent a `tools` array; Open WebUI displayed the result.
Every layer behaved as designed and the output was still invented.

So a result badge in a chat UI is **not** evidence that a real tool ran. Check
the tool name against the tools you actually installed.

## Tuning findings

**`-ub` (ubatch) is the most under-used flag.** Qwen3.6, `-ncmoe 40`, pp4096:

| `-ub` | Prompt tok/s |
|---|---|
| 256 | 416.1 |
| 512 *(default)* | 706.0 |
| 1024 | 1198.0 |

**+70% over the default** for larger VRAM cost. Raise it whenever the context
budget allows; drop to 256 only when squeezing in 1M.

**But this is a claim about CPU-offloaded models, not about ubatch itself.**
The gain comes from amortising expert-weight transfers over PCIe, so it scales
with how much of the model lives in system RAM. On a fully GPU-resident model
there is nothing to amortise: Qwen3.8-27B moves only 1180.7 → 1306.9 across
the same 256 → 1024 range, **+11%**. Check whether you are actually offloading
before paying VRAM for a bigger ubatch — and if you are not, `-ub 256` is a
cheap way to buy back compute buffer for context.

**KV cache type — match them, never mix.** Qwen3.6, `-ncmoe 36`, pp512/tg128:

| `-ctk` / `-ctv` | Prompt tok/s | Gen tok/s |
|---|---|---|
| q8_0 / q8_0 | 776.7 | 33.4 |
| f16 / f16 | 753.0 | 34.8 |
| f16 / q8_0 | 600.9 | 33.2 |
| q8_0 / f16 | 603.6 | 33.0 |

Mixed precision costs ~23% prompt throughput for no memory benefit. q8_0/q8_0
is the right default: same speed as f16, half the memory.

**q4_0 KV is not free, and the cost scales with depth.** The table above says
q8_0 is as fast as f16, which invites assuming q4_0 is as fast again. It is
not. Qwen3.8-27B, `-ub 1024`, tg64, matched depth, nothing else varied:

| Depth | q8_0 | q4_0 | q4_0 cost |
|---|---|---|---|
| 0 | 31.57 | 31.53 | 0% |
| 8K | 30.64 | 27.80 | -9.3% |
| 16K | 29.39 | 25.06 | -14.7% |
| 32K | 27.04 | 20.78 | **-23.1%** |

Zero at depth 0 — there is no cache to read, so the quant cannot matter — and
23% by 32K. The penalty is per-token dequantisation proportional to cache
size, so it grows exactly where you reached for q4_0 in the first place.

**Treat q4_0 KV as the price of admission, never an optimisation.** Use it
only where q8_0 does not fit at all (Qwen3.8 at 128K, Qwen3-Coder-Next at 1M).
Where both fit, q8_0 wins on speed *and* on precision, and only costs VRAM.

**On quality, one negative result.** q4_0 is widely assumed to degrade output,
and a truncated response on the q4_0 preset made that the obvious suspect.
Tested directly: same model, same prompt, same ~13,250-token depth, four
samples per quant, asking for five titled sections of three bullets each plus
a literal end marker.

| KV | Completions | Marker reached | Sections |
|---|---|---|---|
| q4_0 | 1570, 1576, 2500, 2500 | 4/4 | 5/5 each |
| q8_0 | 1573, 1608, 1441, 1590 | 4/4 | 5/5 each |

**No early stopping and no structural loss from q4_0.** If anything it ran
long — two of four runs kept generating past the marker until they hit the
2,500 cap. The real cause of the truncation was the client's `max_tokens`
(above), nothing to do with the KV quant.

Scope: n=4, one task, 13K depth. This says q4_0 does not break long-form
structure at shallow-to-moderate depth. It says **nothing** about factual
accuracy or reasoning, and nothing about 100K+ depth where quantisation error
has far more attention steps to compound through. The measured speed penalty
remains the solid reason to prefer q8_0 wherever it fits.

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

### Rebuilding the ROCm backend

`HIP_PATH` is needed at **both configure and build time**. Every guide shows it
only at configure, which gets you a clean `cmake` run and then fails every `.cu`
file with a misleading `fatal error: 'hip/hip_fp16.h' file not found`:

```bash
cd ~/llama.cpp
HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
  cmake -B build -DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201 -DCMAKE_BUILD_TYPE=Release
HIP_PATH=/opt/rocm cmake --build build -j16
```

Two traps, both of which cost a full build cycle each:

* **`HIPCXX` must point at `clang`, not `clang++`.** Let CMake auto-detect and it
  picks `clang++`, compiles the `.cu` files in CUDA language mode, and dies with
  `unsupported CUDA gpu architecture: gfx1201`.
* **A stale `CMakeCache.txt` survives `git pull`.** When llama.cpp changes how it
  derives HIP include paths, a cache from the previous version keeps "working"
  right up to the point every compile fails on a missing header. `rm -rf
  build/CMakeCache.txt build/CMakeFiles` and reconfigure.

Back up the working binary first (`cp build/bin/llama-server /tmp/`) — a failed
build leaves you with no server at all.

### Serving

Persistent server (OpenAI-compatible API, reachable on the LAN). **Pick the
build by quant format** — `build/` for Q4_K_M, `build-vulkan/` for MXFP4. This
is the raw form; `switch-model.sh` wraps it, and `switch-model.sh router` serves
all presets at once (see [How to switch models](#how-to-switch-models)):

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
`top_k 40`, `min_p 0.01`, repeat penalty disabled. These are Qwen's published
values — `temp 1.0` looks wrong if you habitually lower temperature for code,
but it is tuned for it, and llama.cpp's default `min_p 0.05` is also wrong here.

### Sending a real coding prompt

`coder-prompt.sh` wraps all of the above — system prompt, correct sampling,
file assembly, and a token-budget check that refuses to send rather than let
the reply be truncated mid-function:

```bash
./coder-prompt.sh "add rate limiting to /upload" src/api/*.rs
./coder-prompt.sh -m 8000 "explain how auth flows through this" $(rg -l auth src/)
```

Two rules in its system prompt exist because the model failed without them:
output a unified diff when editing an existing file (asking for "the full
updated file" made it reproduce a 300-line script and blow the token budget
before reaching the change), and never print line numbers in a code block.

It deliberately does **not** ask the model to think step by step —
Qwen3-Coder-Next answers directly, and prompting for a reasoning preamble
fights the training while burning tokens at ~25 tok/s.

### Reading GGUF metadata

Attention topology decides long-context viability, so check it before
downloading anything large:

```bash
~/llama.cpp/build/bin/llama-server -m models/<file>.gguf -c 512 --no-warmup 2>&1 | grep -iE "block_count|full_attention_interval|head_count_kv|key_length|context_length"
```

## How to switch models

`~/llama.cpp/switch-model.sh` and `~/llama.cpp/models-preset.ini` are both
symlinks into this repo — edit them here, run from either path. Keeping the
preset file tracked matters: it carries the verified `-ncmoe`, KV quant,
DFlash and reasoning-budget values for every router preset, so without it a
fresh clone gets the docs and the launcher but none of the configs they
describe.

```bash
~/llama.cpp/switch-model.sh router              # serve ALL presets, switch from the client
~/llama.cpp/switch-model.sh <model> <context>   # pin one: gpt-oss-20b|qwen3.6|gemma4|qwen3-coder|muse-glimmer|qwen3.8
~/llama.cpp/switch-model.sh stop                # SIGTERM, then SIGKILL — frees the GPU
~/llama.cpp/switch-model.sh start               # relaunch whatever ran last
~/llama.cpp/switch-model.sh status              # what's running now
~/llama.cpp/switch-model.sh list                # verified combinations
```

### Router mode is the default worth using

`router` starts one process over every preset in `models-preset.ini`. Picking a
model from Open WebUI's dropdown loads it on demand and unloads the previous one,
so switching needs no shell at all — and each preset carries its full verified
config (`-ncmoe`, KV quant, DFlash, `reasoning_strength`) rather than you
retyping flags.

It costs exactly one thing. The router spawns children from `/proc/self/exe`, so
every model runs on **the binary the router was launched with**. There is no
per-model backend in this mode. Since the router starts from `build/` (ROCm),
gpt-oss-20b at 32k gives up Vulkan's 181 vs 148 tok/s — pin it explicitly with
`switch-model.sh gpt-oss-20b 32k` when you want that back. Every other model
prefers ROCm anyway, so nothing else loses.

Run with `--models-max 1`: this card has 16GB, and a second resident model will
not allocate.

**Correction to an earlier claim in this file:** hot-swapping by changing the
`"model"` field in a request *does* work — that is precisely what the router
does. The no-hot-swap limitation applies only to the pinned single-model mode,
where one `llama-server` holds one model.

### Getting the GPU back without stopping the server

Launches pass `--sleep-idle-seconds 900`. After 15 idle minutes llama-server
calls `destroy()` and releases the model — VRAM drops to ~0 (measured: 12464 →
595 MiB) while the process keeps listening on 8090. The next request calls
`load_model()` and reloads it, so nothing breaks; it just pays a cold start.
This is what makes it safe to leave the server up and go play a game. Upstream's
default is `-1`, disabled; override with `SLEEP_IDLE=<seconds>` or `-1`.

Sleep state is not reported by any endpoint. `/health`, `/props` and `/v1/models`
all pass `create_response(true)`, which deliberately **bypasses** sleep — so they
answer without waking the model, which also means none of them can tell you it
is asleep. `status` infers it from low VRAM against a live process. The useful
consequence: polling `status` never triggers a reload.

This composes with router mode. `--sleep-idle-seconds` is not in
`unset_reserved_args()`, so each spawned child **inherits** it from the router's
own argv (verified in the child's `/proc` cmdline) and releases its own VRAM
after idling, while the router stays up on 8090 serving the full model list.

`stop` covers the router case too. Under `--models-preset` the router spawns a
per-model child that is *also* named `llama-server`, so `pkill -x` matches both.

---

## Model inventory

| Model | Total | Active | Type | Quant | Size | On disk |
|---|---|---|---|---|---|---|
| GPT-OSS-20B | 21B | ~3.6B | MoE | MXFP4 | 11.3GB | yes |
| Qwen3.6-35B-A3B | 35B | ~3B | MoE hybrid, 40L | UD-Q4_K_M | 20.6GB | yes |
| Gemma 4-26B-A4B | 25.2B | ~3.8B | MoE, 30L | UD-Q4_K_M | 15.8GB | yes |
| Qwen3-Coder-Next | 80B | ~3B | MoE hybrid, 48L | UD-Q4_K_M | 49.3GB | yes |
| Muse Glimmer 30B | 30B | 30B | Dense SWA, 52L | UD-Q3_K_XL | 12.4GB | yes |
| Qwen3.8-27B | 27B | 27B | Dense hybrid, 64L | UD-Q3_K_XL | 12.5GB | yes |
| Nemotron-3-Nano-30B-A3B | 31.6B | ~3.5B | MoE Mamba2 hybrid, 52L | UD-Q4_K_XL | 22.8GB | yes |
| Devstral Small 2 24B | 23.6B | 23.6B | Dense, full attn, 40L | Q4_K_M | 14.3GB | yes |
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

---

## Open WebUI

The client this box is driven from, reachable at `http://192.168.4.228:8080`.
Reconstructed from the running container, not from upstream's example:

```bash
docker run -d --network=host \
  -v open-webui:/app/backend/data \
  -e OPENAI_API_BASE_URL=http://127.0.0.1:8090/v1 \
  -e OPENAI_API_KEY=local \
  -e ENABLE_OLLAMA_API=false \
  --name open-webui \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

**`--network=host` is the part that matters.** It is what lets the container
reach `llama-server` at `127.0.0.1:8090` — the same loopback the router binds.
Under default bridge networking that address is the *container's* loopback and
the connection simply fails; you would need `host.docker.internal` plus
`--add-host`, or the LAN IP. Host networking is also why `PORT=8080` publishes
straight onto the host with no `-p` flag.

`OPENAI_API_KEY` is required to be non-empty but never checked — llama.cpp
serves without auth, so `local` is a placeholder. `ENABLE_OLLAMA_API=false`
stops the UI probing for an Ollama backend that is not there.

All chats, settings and uploads live in the named volume `open-webui`, not in
the container. Updating therefore does not lose anything:

```bash
docker pull ghcr.io/open-webui/open-webui:main
docker stop open-webui && docker rm open-webui
# then re-run the command above
```

### Settings that are not in this command

Three things bit hard enough to be worth naming, none of which are container
flags — they live in the UI and are covered in full above:

* **`max_tokens`** (Controls → Advanced Params) is charged for reasoning as
  well as content, so the default silently truncates thinking models
  mid-sentence. See [the client's `max_tokens` is charged for reasoning
  too](#the-clients-max_tokens-is-charged-for-reasoning-too).
* **Code Interpreter** must be enabled in Admin Panel → Settings → Code
  Execution *and* per-chat in the `+` menu. With only the first, the model
  fabricates results with no warning.
* **Function calling** should be set to Native to exercise llama.cpp's own
  parser; the default prompt-based mode succeeds even when the API path is
  broken, which is what made the 2026-04-24 tool-calling bug hard to see.
