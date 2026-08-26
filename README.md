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
| ~~Vulkan~~ | RADV, Mesa 26.1.6 — **retired 2026-08-17** | Its one win was shallow MXFP4 generation; see below |
| **llama.cpp** | `b10463` (`7c35571e5`, 2026-08-17) | Tool calling was broken on `e583f3b4f` and fixed here — see the tool-calling section |

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

**A BIOS update changes none of this — measured.** The board went from BIOS
2407 (July 2021) to 3636 (January 2026), roughly four and a half years of
AGESA updates. Memory still trains at 3200 on all four DIMMs, and Qwen3.6
re-run under identical conditions moved within noise:

| Config | BIOS 2407 | BIOS 3636 |
|---|---|---|
| `-ncmoe 40` prompt / gen | 1198.0 / 31.8 | 1206.1 / 31.0 |
| `-ncmoe 24` prompt / gen | 1616.2 / 39.0 | 1653.9 / 38.6 |

Prompt up 1-2%, generation down 1-2%, both directions — run-to-run variance,
not a change. So 3200 is not a firmware limitation; it is what four
mostly dual-rank DIMMs across two kits will do on this memory controller.
Worth recording because "maybe a BIOS update" is the obvious next thought
when host bandwidth looks like the bottleneck, and on this board it is not
a lever. D.O.C.P is enabled at the G.Skill kit's DDR4-3200 16-18-18-38
profile, which is the correct setting for the slower of two mismatched kits.

**One backend in production: `build/`, `GGML_HIP=ON` (`AMDGPU_TARGETS=gfx1201`).**
`switch-model.sh` routed every model to ROCm on 2026-08-17 and still does —
`BACKEND_OVERRIDE` is an empty hook, no preset points at Vulkan. `build-vulkan/`
itself was deleted that day but has since been rebuilt more than once (same
commit as `build/` each time) to spot-check new models against the routing
decision — see the "Re-verified" notes below. It is not kept installed
permanently; it is a testing tool, rebuilt on demand and removed after.

---

## Headline: ROCm for everything — and why Vulkan was retired

Measured head-to-head, `llama-bench`, **`-fa 1`** throughout (`llama-bench`
defaults flash attention *off*, but `llama-server` resolves `auto → enabled`,
so `-fa 0` numbers do not reflect real serving — an earlier revision of this
file got that wrong):

| Model | Quant | ROCm pp / tg | Vulkan pp / tg | Use |
|---|---|---|---|---|
| Qwen3.6-35B-A3B (`-ncmoe 40 -ub 512`) | Q4_K_M | **706.0** / — | 333.4 / 29.3 | ROCm |
| Gemma 4-26B-A4B (`-ncmoe 8`) | Q4_K_M | **1949.9** / **50.3** | 1064.7 / 48.0 | ROCm |
| GPT-OSS-20B, shallow | MXFP4 | **5529.9** / 148.5 | 4952.0 / **180.8** | *was Vulkan* |
| GPT-OSS-20B, @131k depth | MXFP4 | **1035.2** / **70.5** | 1063.7 / 22.3 | **ROCm** |
| Qwen3.8-27B, dense (`-ngl 99`) | Q3_K_XL | **1329.4** / **30.64** | 1161.8 / 16.91 | ROCm |
| Laguna XS.2 33B-A3B (`-ncmoe 16`) | Q4_K_M | **1244.4** / **55.28** | 661.7 / 48.19 | ROCm |

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
`switch-model.sh` used to route `gpt-oss-20b:128k` to ROCm while leaving 32k on
Vulkan.

### Why it was retired (2026-08-17)

Vulkan's only remaining advantage was shallow MXFP4 generation — 180.8 vs 148.5
tok/s — and that applied to exactly one preset: `gpt-oss-20b` pinned at 32k.
Router mode always spawned children from the ROCm binary, so in day-to-day use
that advantage was never actually being collected. Against it:

* ROCm wins prompt outright at every depth (5529.9 vs 4952.0 shallow).
* ROCm wins 128k generation by **3.2x** (70.5 vs 22.3).
* Keeping two builds means two rebuilds per upgrade, and the Vulkan tree had
  already drifted two commits behind the ROCm one before anyone noticed.

So `gpt-oss-20b` moved to ROCm and `build-vulkan/` was dropped, trading 18% of
shallow generation on one preset for a single backend with no version skew.
`BACKEND_OVERRIDE` remains in `switch-model.sh` as an empty hook in case a
future model reverses the argument.

Combining the ROCm switch with `-ncmoe`/`-ub` tuning gives **4.8x prompt /
+33% generation** over the old Qwen3.6 config (333.4/29.3 → 1616.2/39.0) — but
note the generation share of that comes from `-ncmoe 40 → 24`, not the backend.

**All Vulkan numbers at the bottom of this file are superseded.**

### Re-verified since retirement (2026-08-25)

`build-vulkan/` gets rebuilt from scratch on demand (`cmake -DGGML_VULKAN=ON`,
same checkout/commit as `build/` each time — so unlike the drift that partly
motivated the original retirement, these are not version-skew comparisons),
spot-checked against a model, then removed again. Two models tested so far
that hadn't been benched under Vulkan before:

* **Qwen3.8-27B**, dense Q3_K_XL: ROCm wins prompt by 14% (1329.4 vs 1161.8)
  and **generation by 81%** (30.64 vs 16.91) — the widest generation gap of
  any model in the table above.
* **Laguna XS.2 33B-A3B**, Q4_K_M (`-ncmoe 16`): ROCm wins prompt by **88%**
  (1244.4 vs 661.7) — the widest prompt gap of any model in the table — and
  generation by 15% (55.28 vs 48.19).

Both confirm the routing decision: ROCm stays the only backend `switch-model.sh`
spawns.

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
| Qwen3.8-27B | 262,144 | **VRAM-capped here** — 131,072 at `UD-Q3_K_XL`, **196,608 at `UD-IQ3_XXS`** (measured 2026-08-21). 262,144 does not fit at any quant tested |
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
  llama.cpp discards it *by default* — `model has unused tensor blk.64.*
  -- ignoring`. That is **198.8 MiB** of the file you store and normally never
  execute.
  > **Corrected 2026-08-21.** This section used to say the model's own
  > speculative-decoding mechanism was "unavailable, unlike Muse Glimmer where
  > DFlash is first-class". That is wrong on build `b10463`. The `ignoring`
  > message is the default-off path, not a missing feature:
  > `src/models/qwen35.cpp:97` has `load_block_mtp`, gated on `ml.load_mtp`,
  > which `--spec-type draft-mtp` sets. It works, and it is worth **2.40x**
  > generation — see the Dynamic 3.0 section below. It is also far more
  > expensive than the 198.8 MiB of weights suggests.
* Unsloth's `UD-Q3_K_XL` reports internally as `Q4_K - Small` at 3.93 BPW.
  The name is the recipe, not the block type; do not match on it.
  > **This is Dynamic 2.0-specific.** The Dynamic 3.0 re-quant of the same
  > filename reports `Q3_K - Large` at 3.80 BPW. Both are correct for their
  > vintage, which is the point: the filename does not identify the build.

### Qwen3.8-27B, Unsloth Dynamic 3.0 — measured 2026-08-21

`unsloth/Qwen3.8-27B-GGUF` was re-quantised in place on **2026-08-19/20** with
Unsloth's Dynamic 3.0 recipe. **Same repo, same filenames.** A file pulled on
2026-08-16 is Dynamic 2.0 and nothing in its name says so, so the only reliable
check is the byte size or the LFS oid — see `Reading GGUF metadata` below.

Both builds of `UD-Q3_K_XL`, read straight out of the GGUF headers:

| | v2 (pulled 08-16) | v3 (pulled 08-21) |
|---|---|---|
| File bytes | 13,441,059,904 | 13,146,393,504 |
| `general.file_type` | 14 → `Q4_K - Small` | 13 → `Q3_K - Large` |
| `quantize.imatrix.chunks_count` | **45** | **1,251** |
| Distinct ggml quant types | 5 | **14** |
| Trunk BPW (blk.0-63, excl. MTP) | 3.932 | 3.802 |

The imatrix jump 45 → 1,251 chunks is Unsloth's "higher-quality calibration
dataset" claim, sitting in the metadata where it can be checked. The recipe
went from a blunt IQ4_XS/IQ3_S split to fourteen types — 96 small tensors
pinned at Q8_0 (24 MiB total) while large FFN tensors drop to IQ2_S/IQ3_XXS.

**The VRAM saving is bigger than the file shrank, and that is the non-obvious
part.** Unsloth spent *more* on the MTP head while cutting the trunk harder,
and llama.cpp skips `blk.64` unless you ask for it:

| Loaded portion | v2 | v3 | Δ |
|---|---|---|---|
| Trunk (blk.0-63 + embd + output) | 12,609.1 MiB | 12,192.1 MiB | **−417.0** |
| `blk.64` MTP head (skipped by default) | 198.8 | 334.7 | +136.0 |
| File total | 12,807.9 | 12,526.9 | −281.0 |

Measured against a real load, v3 gives back **391 MiB** at 32K (14,409 →
14,018 model-attributable), not the 417 the headers predict — the 26 MiB gap
is buffer alignment. Predicting from headers is a good first cut, not a
substitute for `fit.sh`.

**v3 costs 3.6% of generation, reproducibly.** Same 700-token code prompt,
`-ub 1024`, q8_0 KV, 32K, n=3 each:

| | run 1 | run 2 | run 3 | mean |
|---|---|---|---|---|
| v2 | 30.75 | 30.77 | 30.81 | **30.78** |
| v3 | 29.70 | 29.69 | 29.61 | **29.67** |

Standard deviation is ~0.05, so this is outside noise. Fourteen quant types
means more dequant paths than five. You are buying VRAM with throughput.

What the 391 MiB actually buys — every row measured, baseline-subtracted:

| Context | v2 shipped | v3 measured | Verdict |
|---|---|---|---|
| 32K, q8_0 | `-ub 1024`, 14,409 | `-ub 1024`, 14,018 (2,023 free) | more headroom, same config |
| 64K, q8_0 | `-ub 512`, 493 free at `-ub 1024` | **`-ub 1024`, 15,295 (746 free)** | upgrade `-ub` |
| 128K, q4_0 | `-ub 256`, 281 free | **`-ub 512`, 15,665 (376 free)** | upgrade `-ub` |
| 128K, q8_0 | impossible | still impossible | needs +2,176 MiB |

Both `-ub` upgrades are worth ~12% prompt by the ubatch sweep further down.
**v3 buys prefill speed at 64K/128K, not more context.**

Rejected past 128K, all measured on v3 `UD-Q3_K_XL`:

| Attempt | Result |
|---|---|
| 144K, q4_0, `-ub 256` | 15,921 — **106 MiB free**, trap zone |
| 160K, q4_0, `-ub 256` | loads at **16,275 (29 MiB free)** with 150 MiB already on GTT |
| 176K, q4_0, `-ub 256` | fails — compute pp buffers |

#### The 160K row exposed a hole in `fit.sh`

`fit.sh` scored that 160K config a **pass at `model=13313`, 2,707 MiB free**.
It is not a pass. VRAM at load was 16,275 MiB and GTT rose 275 → 425 MiB:
buffers migrated to host memory, and because `fit.sh` reads `PEAK` *after* the
probe returns, it measured the post-migration figure and reported a comfortable
fit. The `loaded=` column caught what the headline `model=` column hid.

Reproduced twice. **A row is only trustworthy if `peak >= loaded` and GTT has
not moved.**

**Fixed 2026-08-21.** `fit.sh` now samples GTT alongside VRAM and refuses any
row where `peak < loaded` or GTT drifted past `GTT_TOLERANCE` (48 MiB; desktop
GTT moved <10 MiB across a whole session, a real spill moved 150). It prints
`SPILL` and exits non-zero. Regression-tested both directions — the 128K
control still passes at `free=372, gtt+6`, and the 160K row now fails with
`free_at_load=14, gtt+150`. Note the `peak < loaded` signature only tripped by
1 MiB on the re-run, so the GTT check is the one doing the work; both are kept
because they fail independently.

#### MTP speculative decoding: 2.40x, and it needs no new download

`blk.64` is present in **both** v2 and v3, so this is testable on a file you
already have. `--spec-type draft-mtp` on build `b10463`:

| Config | Generation | Interactive follow-ups |
|---|---|---|
| v2 @16K, no MTP | 30.82 tok/s | 2.3-2.6s |
| **v2 @16K, MTP** | **74.02 tok/s (2.40x)** | — |
| v3 @16K, no MTP | 29.70 tok/s | 2.3-2.6s |
| **v3 @16K, MTP** | **69.47 tok/s (2.34x)** | **0.9-1.1s** |

That beats Muse Glimmer's DFlash (1.64x) and puts this model's follow-up
latency level with GLM-4.7-Flash's 1.1-1.2s.

**The cost is ~2,212 MiB, fixed.** Not the 198.8 MiB of `blk.64` weights —
`common_speculative_init_result` builds a second full context. Measured
identical at 8K and 16K, and unchanged by `-b 2048` vs `-b 512`, so it does not
scale with context or batch. On a 16 GB card holding 12.5 GB of weights that
caps MTP at **16K**:

| Attempt | Result |
|---|---|
| v3 16K, q8_0, `-ub 512`, MTP | **376-415 MiB free** — shippable |
| v2 16K, q8_0, `-ub 512`, MTP | 140-158 MiB free |
| v3 32K, MTP | **SPILL** — `free_at_load=28`, GTT **+12,154 MiB** |
| v3 24K, MTP | 95 MiB free — do not ship |
| v2 32K, MTP | fails outright |
| IQ4_XS 8K, MTP | fails outright — no MTP on this tier at any context |

> **Corrected 2026-08-21, by the GTT guard.** The v3-32K-with-MTP row was
> originally recorded here as "fit.sh passes at 33 MiB free, do not ship". It
> does not pass. Re-measured with the spill guard it dumps **12 GB** to host
> memory — `free_at_load=28, gtt+12154`. The conclusion (do not ship) was
> right; the reason was much worse than the number suggested. Any pre-guard
> row in this file quoting single- or double-digit free VRAM should be treated
> the same way until re-measured.

v3 + MTP at 16K verified under a real **14,358-token** prompt: 5/5 needle,
peak 15,927 MiB, no OOM. **This is the config to pick if you want speed and can
live inside 16K.** If you cannot, MTP is not for you — the 2.2 GB is not
negotiable.

#### Trading tier down for context: `UD-IQ3_XXS` reaches 192K

The interesting move for long-context work is not v3 at the same tier, it is
v3 at a *lower* tier, because Dynamic 3.0's whole claim is that low-bit quants
hold up. Trunk sizes and BPW, from the headers:

| Quant (v3) | Trunk MiB | Trunk BPW | Max context measured |
|---|---|---|---|
| `UD-IQ4_XS` | 13,247.3 | 4.131 | 32K q8_0 / 64K q4_0 |
| `UD-Q3_K_XL` | 12,192.1 | 3.802 | 128K q4_0 |
| `UD-IQ3_XXS` | 10,093.0 | **3.148** | **192K q4_0** |

Measured fits:

| Config | Model MiB | Free |
|---|---|---|
| IQ4_XS 32K, q8_0, `-ub 1024` | 15,070 | 955 |
| IQ4_XS 64K, q4_0, `-ub 512` | 15,247 | 780 |
| IQ4_XS 64K, q8_0, `-ub 512` | **SPILL** | `free_at_load=9`, GTT **+2,314 MiB** |
| IQ4_XS 128K | fails | — |
| IQ3_XXS 128K, q4_0, `-ub 512` | 13,886 | 2,141 |
| **IQ3_XXS 192K, q4_0, `-ub 512`** | **15,355** | **672** |
| IQ3_XXS 256K, q4_0, `-ub 512` and `-ub 256` | fails | — |

**192K holds more headroom (672 MiB) than the shipped 128K preset does (281).**
Native 262,144 remains unreachable, so the claim above still stands — but the
ceiling moved from 131,072 to 196,608.

The obvious worry is that 3.148 BPW is too aggressive to retrieve at that
depth. It is not, on these probes:

| Probe | Result |
|---|---|
| Needle | **5/5 at 189,482 tokens**, peak 15,656 MiB, GTT flat at 275 (no spill) |
| Semantic | **5/5 at 186,695 tokens** — retrieval by meaning against near-miss distractors |
| Tool calling | single ✓ `PROBE-770487`, parallel ✓ sum `1,355,528`, three calls with `add_numbers` delegation |
| Generation, shallow | 28.94 tok/s |

**The cost is prefill, and it is steep.** Cold prefill of that 189K haystack
took **686 seconds** (~276 tok/s). Cached follow-ups are 5.3-6.2s (needle) and
4.9-8.8s (semantic). This is a "load the codebase once and work in it" config,
not one to rebuild the prompt against.

`UD-IQ3_XXS` is the same Dynamic 3.0 build as `UD-Q3_K_XL` — identical imatrix
(1,251 chunks), byte-identical chat template, `general.file_type` the only
differing KV key. It is a clean tier comparison, not a different vintage.

#### Which one to run

| Want | Take | Why |
|---|---|---|
| Max context | **`UD-IQ3_XXS` @192K, q4_0, `-ub 512`** | 1.5x the old ceiling, 672 MiB free, 5/5 on both recall probes |
| Max speed, ≤16K | **`UD-Q3_K_XL` v3 + `--spec-type draft-mtp` @16K** | 2.34x generation, ~1s follow-ups |
| Balanced 32K-128K | `UD-Q3_K_XL` v3, `-ub` upgraded | 391 MiB back, ~12% prompt, −3.6% generation |
| Best weights ≤32K | `UD-IQ4_XS` | 4.131 BPW, 30.35 tok/s, 955 MiB free |
| Nothing changes | stay on v2 | it is 3.6% faster at generation than v3 |

**What none of this measures.** Every probe here tests *retrieval*, not
generation quality. All three quants score 5/5 on needle and semantic at 32K —
the probes are saturated and cannot separate them. Unsloth's ">10% top-1%
accuracy" claim is neither confirmed nor refuted by anything in this section;
that needs KLD or perplexity against the 54 GB BF16.

### Qwen3.5-27B-Uncensored (HauhauCS, Aggressive) — 12.4GB, **dense** 27B, 64 layers

`HauhauCS/Qwen3.5-27B-Uncensored-HauhauCS-Aggressive`, Q3_K_M, added
2026-08-18. Arch is `qwen35` and it reports 26.90B params over 64 layers with
the same 3:1 hybrid-attention ratio as Qwen3.8-27B — so it is that model's
architectural twin one base version back, and the two are directly comparable
on this card. SHA256 verified against the HF-reported LFS oid.

Q3_K_M was chosen the same way Qwen3.8 landed on Q3_K_XL: Q4_K_M is 16.54GB
and cannot fit at any context, IQ4_XS is 14.69GB and would leave ~300 MiB, and
Q3_K_M at 13.29GB is within 150 MiB of the file already proven to fit.

**VRAM figures here are baseline-subtracted, and that is a change.** See the
note below on why the raw column in the older sections is not reproducible.

| Context | Extra flags | Model MiB | Free at base 701 |
|---|---|---|---|
| 32K | `-ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,476 | 1,127 |
| 64K | `-ub 512 -b 2048 -fa on -ctk q4_0 -ctv q4_0` | 14,657 | 946 |
| *128K* | `-ub 256 -b 2048 -fa on -ctk q4_0 -ctv q4_0` | 15,571 | **32** |

Rejected, measured:

| Attempt | Result |
|---|---|
| 64K, q8_0, `-ub 512` | model 15,608 — **55 MiB free** when measured, negative at the session's worst baseline |

**64K cannot run q8_0 here, and that is the one place this model diverges from
Qwen3.8.** Qwen3.8 deliberately takes q8_0 at 64K and accepts 761 MiB free,
because q4_0 costs up to 23% of generation at depth. This model is 266 MiB
heavier at the same context and that trade is no longer available — q8_0 at
64K leaves 55 MiB, which is inside the noise of desktop VRAM drift. So the 64K
preset takes q4_0 and the documented generation penalty with it. At 32K the
gap is only 67 MiB and the q8_0 config is comfortable.

**128K is listed but should not be a preset.** 32 MiB of headroom is smaller
than the baseline drift measured *during this session* (see below), so it is
in the same category as the Muse Glimmer + DFlash case: it loads, it answers,
and any other GPU consumer breaks it.

#### The raw VRAM column in the older sections is not reproducible — the baseline moved

`fit.sh` was lost and has been rewritten (it is now committed rather than
living in a scratchpad). Calibrating it against the known Qwen3.8-27B 32K row
before trusting it produced a 440 MiB disagreement — 15,050 measured against
14,610 published. The cause is not the script:

| | Published | Re-measured |
|---|---|---|
| Raw peak | 14,610 | 15,050 |
| Desktop baseline | ~201 (implied) | 641 |
| **Model-attributable** | **14,410** | **14,409** |

The model-attributable figure reproduces to **1 MiB**. What moved is the
desktop's own VRAM, which every "VRAM used / Free" number in the older
sections silently includes. That baseline was observed at **395, 641 and 701
MiB at different points in this one session** — a 306 MiB spread, which is
larger than the stated headroom of several published configs and larger than
the entire 128K margin above.

This does not invalidate the older rows; each was true against whatever the
desktop held that day. But it means the `Free` column there is a measurement
of the machine's state, not of the model, and configs with sub-300 MiB margins
are less reproducible than they read. New rows report model-attributable VRAM
and state the reference baseline.

### Qwen3.5-9B-Uncensored (HauhauCS, Aggressive) — 8.9GB, **dense** 9B, 32 layers

`HauhauCS/Qwen3.5-9B-Uncensored-HauhauCS-Aggressive`, Q8_0, added 2026-08-18.
SHA256 verified against the HF-reported LFS oid. Same `qwen35` family as
Qwen3.8-27B and the 27B-Uncensored above, but at 8.95B params over 32 layers —
**half the layer count, and the same 3:1 hybrid-attention ratio** gives 8
layers with KV instead of 16. Head count and head dim are unchanged (4 KV
heads × 256), so the per-token KV cost is exactly half its bigger sibling's:
**17,408 B/token at q8_0** against the 27B's 34,816.

Q8_0 (9.53GB) was chosen deliberately over a smaller quant. Unlike the 27B,
VRAM was never the constraint here — weights this light leave room to ask
what the model can reach, not what it can be shrunk to fit.

**This is the first dense model on this card to reach its full native context
at full KV precision.** Every other native-262144 model that gets there
(Qwen3.6, Qwen3-Coder-Next, Gemma 4) is MoE and pays for it in disk size
(16.9-49.3GB); every dense hybrid-attention model (Qwen3.8, the 27B-Uncensored
above) is VRAM-capped well short of native. This 9B is dense **and** reaches
262,144 — the halved KV cost is why.

| Context | Extra flags | Model MiB | Free at base 476-536 |
|---|---|---|---|
| 32K | `-ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 9,384 | 6,444 |
| 128K | `-ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 11,587 | 4,181 |
| 256K *(native)* | `-ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,524 | 1,304 |

No `-ub` reduction was needed at any context — even at 262,144 the compute
buffer fits comfortably under `-ub 1024`, unlike the 27B twin, which had to
drop to `-ub 256` just to reach 128K. **q8_0 KV holds at every context here**;
there was never a q4_0 tradeoff to make.

Verified under real load, not just the allocation probe: 5/5 needle recall at
216,208 tokens and 5/5 semantic recall (against near-miss distractors) at
225,148 tokens, both against the 256K preset, both with no OOM. See Context
quality below for the full numbers.

Thinking model, same profile as its family: `enable_thinking`, no
`reasoning_effort`, so `--reasoning-budget` is required for the same reason
documented under Qwen3.8.

### Nemotron-3-Nano-30B-A3B — 22.8GB, MoE 31.6B/~3.5B active, Mamba2 hybrid

**Deleted from disk (2026-08-17)** — kept here because the throughput and
fitting measurements below are still correct and still the cheapest 1M-context
config in this file. It was not removed for anything in this section.

The reason is in [`real-world-testing.md`](real-world-testing.md#when-feedback-is-gamed-nemotron-fabricates-a-dataset):
run agentically through Cline, it fabricated a full dataset of pre-2024 models
with real citation URLs attached to invented scores, after its real data
source failed to resolve — and separately falsified a "clean" verification
report, claiming files existed and checks passed when they had not, on two
occasions. Neither is a benchmark-quality problem; both are about whether the
model's *reports of its own actions* can be trusted, which every number on
this page assumes.

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

### GLM-4.7-Flash — 16.3GB, MoE 30B/~3B active, `deepseek2` arch (MLA attention)

`unsloth/GLM-4.7-Flash-GGUF`, UD-Q4_K_XL, added 2026-08-18. SHA256 verified
against the HF-reported LFS oid. First non-Qwen model in this file, and the
first to use **Multi-head Latent Attention** rather than GQA or a hybrid
SSM/attention split. Reports as `deepseek2` in llama.cpp — it reuses
DeepSeek-V2's MLA implementation rather than a GLM-specific code path — which
matters because it means every number below is really testing this repo's
first look at MLA, not GLM specifically. Native context 202,752, 47 layers (1
leading dense, 46 MoE), 64 experts with 4 active. Already supported by this
build (`LLM_ARCH_DEEPSEEK2`) — no rebuild needed, same as every model so far.

**MLA's KV cache is a single compressed latent per layer, not per-head K and
V.** `kv_lora_rank = 512` plus a 64-dim decoupled RoPE component gives 576
elements/layer/token, applied at **every** layer (unlike the qwen35 hybrid
models, which skip 3 of every 4). Measured empirically by comparing
model-attributable VRAM at fixed `-ncmoe` across two contexts (32K and 128K,
`-ncmoe 16` both times): **≈27,915 B/token**, within 3% of the
576×47×1.0625(q8_0) = 28,764 B/token formula. That's **cheaper than Qwen3.8's
34,816 B/token**, despite running at every layer instead of a sparse subset —
compression wins over sparsity here. **q8_0 KV quantization works for MLA on
this build** — not something I'd have assumed going in; the first attempt at
`-ncmoe 4` failed to allocate, but that was a plain VRAM shortfall (the error
named the KV buffer, not the type), confirmed by the exact same flags
succeeding at `-ncmoe 16`.

The weights (17.52GB) exceed 16GB VRAM by only ~800 MiB — the smallest deficit
of any MoE model in this file — so `-ncmoe` needed is far lower than Qwen3.6's
floor of 16, despite a comparable total file size:

| Context | Extra flags | Model MiB | Free |
|---|---|---|---|
| 32K | `-ncmoe 12 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,357 | 1,337 |
| 128K | `-ncmoe 20 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,743 | 1,130 |
| 202,752 *(native)* | `-ncmoe 28 -ub 512 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,017 | 1,856 |

Rejected, measured: `-ncmoe 8` at 32K loads at 15,649 MiB — **45 MiB free**,
the same fragile territory already flagged for the 27B-Uncensored's 64K and
128K configs. `-ncmoe 16` at 128K is worse — **19 MiB free**. `-ncmoe 24` at
native context gives only 534 MiB free; `-ncmoe 28` was chosen instead for
1,856 MiB, a real margin, for a ~4-layer CPU-offload cost.

Verified under real load, not just the allocation probe: 5/5 needle recall at
29,817 tokens and 5/5 semantic recall at 27,185 tokens, both against the 32K
preset.

Sampling: Z.ai's own recommendation is `--temp 1.0 --top-p 0.95` for general
use, `--temp 0.7 --top-p 1.0` for tool-calling specifically, and
`--min-p 0.01` on llama.cpp (its default of 0.05 is higher than upstream's).
`--repeat-penalty 1.0` (disabled) is also recommended. All tests here ran the
general-use params, including the tool-calling probe — a single preset
serving both isn't unusual, but a config tuned purely for tool-calling
throughput would use the vendor's other numbers. Same thinking profile as the
rest of this file: `enable_thinking`, no `reasoning_effort`, so
`--reasoning-budget` and `--no-think` work the same way they do for the Qwen
models.

### Devstral Small 2 24B — 14.3GB, **dense** 24B coding specialist, Apache 2.0

**Deleted from disk** — kept here because the measurements stand. It was
removed for its 32K ceiling, not for capability: it is the fastest coder
measured on this box, and on the one head-to-head quality test it scored
better than Qwen3-Coder-Next. Re-downloading is ~16 minutes if that trade
ever looks worth it again.

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

### Laguna XS.2 (Poolside) — 18.9GB, MoE 33B/~3B active, agentic coding, `laguna` arch

Poolside's own local-scale model, released 2026-07-21. **Every Laguna is MoE** —
there is no dense variant — and three sizes exist:

| Variant | Total / active | Layers | Attention | Verdict here |
|---|---|---|---|---|
| **Laguna XS.2** (XS-2.1) | 33B / 3B | 40 | hybrid, 10 full + 30 SWA(512) | tested, below |
| Laguna S 2.1 | 118B / 8B | — | hybrid | see below |
| Laguna M.1 | 225B / 23B | 70 | **global on all layers**, 64 Q / 8 KV | out of reach |

Q4_K_M is the only quant Poolside ships for XS besides BF16 (66.9GB) — no
Q5/Q6/Q8 official tier, unlike every other model in this file.

**Why S was not tested, 2026-08-23.** Poolside's own Q4_K_M is 68GB against
62GB of system RAM, so the official quant is out. But bartowski publishes the
full ladder, and the 3-bit tier *would* fit: `Q3_K_S` 51.6GB or `IQ3_XXS`
49.5GB, both single-file, against ~57GB available RAM plus 15.8GB VRAM. The
blocker is not fit, it is speed — S activates **8B** per token against XS's 3B,
and with 118B of routed experts essentially all CPU-resident, generation lands
around 5-9 tok/s versus XS's 47. That is a considered-single-answer model, not
an agentic-loop one, and XS's suite results below did not justify the 50GB
download. M.1 is doubly out: 225B, and global attention on all 70 layers means
KV cost scales the way Gemma 4's does rather than the way XS's hybrid does.

`laguna` architecture support landed in upstream llama.cpp on 2026-07-22
(#25165) and this box's exact checkout (`b10463`, `7c35571e5`) already has it
compiled into `libllama.so` — no rebuild was needed.

Hybrid attention, 40 layers: 10 full-attention (period 4, dense-first) + 30
sliding-window (512 tokens), **8 KV heads x 128 dim** — 4x Qwen3.6's 2 KV
heads, so KV costs more per token despite the same layer-count fraction.
Context is 262,144 (matches GGUF `laguna.context_length`), but that number is
already a YaRN 32x stretch from an 8,192 base — same caveat as GPT-OSS-20B's
131,072, not a directly-trained ceiling.

| Context | Extra flags | VRAM used | Free |
|---|---|---|---|
| 32K | `-ncmoe 16 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,418 | 1,886 |
| 128K | `-ncmoe 20 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 15,058 | 1,246 |
| 256K | `-ncmoe 26 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 15,814 | 490 |

256K's 490 MiB free is thinner than most rows in this file but passed `fit.sh`
clean (`peak >= loaded`, GTT flat) — a real fit, just not a roomy one.

**Thinking defaults off in the template** (`enable_thinking | default(false)`)
but the server does not honour that default on its own: a plain request burned
its entire 800-token budget on reasoning and returned zero content, the same
trap documented for Qwen3.8 and Muse Glimmer above. Fix is
`"chat_template_kwargs": {"enable_thinking": false}` — every probe script in
`benchmarks/` already sends it, so the suite runs against Laguna unmodified.

**The GGUF does embed sampling defaults**, unlike Muse Glimmer above:
`general.sampling.temp = 1.0`, `top_p = 1.0`, `min_p = 0.0`. Every probe here
sends `temperature: 0.0` in the request body, which overrides both those and
the server's `--temp`, so the scores below are greedy and directly comparable
to every other row — but a client that sends no temperature will inherit 1.0.
Other metadata worth knowing: `general.size_label` is `256x2.2B`, and
`general.name` is a bare git hash rather than a model name, which is why
`llama-bench` labels it from the architecture as `laguna 30B.A3B`.

**Native tool calling verified, single and parallel.** Single
`get_probe_token(seed=42)` → `PROBE-770487`; parallel → three calls
(`PROBE-439563`, `PROBE-915965`, then `add_numbers` → `1355528`), all
arguments correct. This is the strongest axis measured on the model.

**Coding quality is the weakest in this file, and that is the model, not the
quant.** The full suite ran on 2026-08-23 at both `Q4_K_M` (Poolside's own)
and `Q8_0` (bartowski, imatrix) — raw output in
`benchmarks/laguna-XS-2.1-Q4_K_M/` and `benchmarks/laguna-XS-2.1-Q8_0/`:

| Probe | Q4_K_M | Q8_0 | Field |
|---|---|---|---|
| `code-quality` | 27/50 (54%) | **27/50 (54%)** | 30-38/50 (60-76%) |
| `cdn-freshness` | 18/36 (50%) | **27/36 (75%)** | 30-39 URLs (83-93%) |
| tool calling | single + parallel ✓ | single + parallel ✓ | ✓ for all tested |
| throughput (700 tok) | **47.0 tok/s** | 30.2 tok/s | 24.7-30.6 tok/s |

**Q8_0 was run specifically to test whether Poolside's Q4_K_M was holding the
model back. It was not — for coding.** The 54% is identical at a quant that
is effectively lossless, so Laguna genuinely sits below every other model here
on differential stdlib reimplementation. The aggregate hides large per-task
churn and the `SyntaxError` seen at Q4_K_M does *not* recur at Q8_0; see the
code-quality section for the full breakdown.

**Library knowledge is a different story — that one was the quant.**
`cdn-freshness` gained 25 points at Q8_0, dropping three of six hallucinated
CDN paths. Version-string recall degrades under quantisation well before
coding ability does.

An earlier note in this section credited Laguna with "correct, complete code"
on the strength of a single bracket-balance prompt — that prompt was too easy
to support the claim, which is why the differential suite exists.

**Choosing between them.** Q4_K_M is the speed pick at 47 tok/s and 19GB.
Q8_0 costs 33GB on disk and drops to 30.2 tok/s — still top of the field —
and buys materially better library knowledge for no change in coding quality.
Because Q8_0 pushes more experts to CPU, it is also the *roomier* fit at long
context: 1,348 MiB free at 256K against Q4_K_M's 490.

| Q8_0 context | Extra flags | VRAM used | Free |
|---|---|---|---|
| 32K | `-ncmoe 26 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 15,556 | 748 |
| 128K | `-ncmoe 30 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,732 | 1,572 |
| 256K | `-ncmoe 34 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0` | 14,956 | 1,348 |

The GGUF is **93.8% expert tensors** (0.777 GiB per layer at Q8_0), which is
why a 33GB model runs at all on a 16GB card — `-ncmoe` moves the bulk into
system RAM and VRAM stays roughly flat. That ratio also makes the fit
predictable: `0.064*T + (40-N)*0.936*T/40 + KV` sized every row above to
within 1% before it was measured.

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

### Laguna XS.2 — `-ub 1024`, q8_0 KV, pp4096/tg64

| `-ncmoe` | Prompt tok/s | Gen tok/s |
|---|---|---|
| 16 | 2074.9 | 46.7 |
| 20 | 1846.1 | 43.7 |
| 26 | 1618.4 | 39.3 |

Faster than Qwen3.6-35B-A3B at every matched `-ncmoe` (2074.9 vs 1974.8 at 16,
1618.4 vs 1616.2 at 24/26) despite an almost identical 18.9GB/20.6GB file
size — Laguna's 512-wide expert FFN is lighter per active parameter than
Qwen3.6's.

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

### Qwen3.5-27B-Uncensored — ROCm, `-fa 1`, pp4096/tg64

Ubatch sweep at q8_0 KV, shallow — run against Qwen3.8-27B, its architectural
twin, at identical settings:

| `-ub` | Prompt | Gen | Qwen3.8 prompt | Qwen3.8 gen |
|---|---|---|---|---|
| 256 | 1031.5 | 29.7 | 1180.7 | 31.9 |
| 512 | 1131.8 | 29.7 | 1279.7 | 31.9 |
| 1024 | 1153.6 | 29.5 | 1306.9 | 31.9 |

**~12% slower prompt, ~7% slower generation than Qwen3.8 across the board.**
It also reproduces Qwen3.8's `-ub` finding — +12% across the whole range,
versus +188% on Qwen3.6 — which is the expected signature of a dense,
fully-GPU-resident model with no host traffic to amortise.

Depth sweep, q8_0 KV, `-ub 1024` (the 32K preset):

| Depth | Prompt | Gen | Qwen3.8 gen, q8_0 |
|---|---|---|---|
| 0 | 1179.4 | 29.8 | 31.6 |
| 8K | 922.7 | 28.1 | 30.6 |
| 16K | 757.1 | 26.7 | 29.4 |
| 32K | 552.8 | **24.5** | 27.0 |

Decay across the range is **1.21x**, against Qwen3.8's 1.17x — the same shape,
slightly worse, and both far better than the 3.3x that Qwen3.8 shows out to
131K on the q4_0 curve. Prompt throughput at depth is effectively identical to
Qwen3.8 (552.8 vs 551.2 at 32K); the deficit is concentrated in generation.

### Qwen3.5-9B-Uncensored — ROCm, `-fa 1`, pp4096/tg64

Ubatch sweep at q8_0 KV, shallow:

| `-ub` | Prompt tok/s | Gen tok/s |
|---|---|---|
| 256 | 3884.6 | 56.2 |
| 512 | 4270.3 | 56.3 |
| 1024 | 4423.4 | 56.2 |

Generation is flat across `-ub` — same dense-model signature as its 27B
sibling — but **1.9x its generation speed** (56.2 vs 29.5 at `-ub 1024`)
against 3x fewer parameters (8.95B vs 26.90B). Not a clean params-scaling
result: the 27B runs Q3_K (12.37GiB resident) against this model's Q8_0
(8.86GiB), and quant format changes both bytes-per-token bandwidth and
per-token dequant compute, so this compares two different points on the
size/speed curve, not "the same model, smaller."

Depth sweep, q8_0 KV, `-ub 1024`, out to the **native ceiling**:

| Depth | Prompt tok/s | Gen tok/s |
|---|---|---|
| 0 | 4353.5 | 56.6 |
| 32K | 1742.2 | 49.1 |
| 131K | 630.4 | 35.7 |
| 262,080 | 343.6 | **25.8** |

**Decay across the full native range is 2.2x** (56.6 → 25.8). Compare the
27B-Uncensored's 1.21x decay to just 32K, or Qwen3.8's 3.3x to 131K on the
q4_0 curve — this model decays over **double the depth range** of either and
still lands ahead of Qwen3.8's worst-case 9.6 tok/s at 131K. The halved
per-token KV cost is doing real work here, not just a fit-headroom number.

### GLM-4.7-Flash — ROCm, `-fa 1`, pp4096/tg64, q8_0 KV

`-ncmoe` sweep, shallow, same style as Qwen3.6's table:

| `-ncmoe` | Prompt tok/s | Gen tok/s |
|---|---|---|
| 28 | 1243.6 | 28.7 |
| 24 | 1318.7 | 32.3 |
| 20 | 1375.6 | 35.9 |
| 16 | 1463.2 | 39.0 |
| 12 | 1571.9 | 43.3 |

Monotonic, same shape as Qwen3.6 — but GLM reaches Qwen3.6's *best* published
generation figure (43.9 tok/s at `-ncmoe 16`) at `-ncmoe 12`, needing 4 fewer
GPU-resident layers to get there. Consistent with the file being 4.6GB
lighter (17.52GB vs Qwen3.6's 22.1GB): less has to move to hit a given
residency level.

Depth sweep, `-ncmoe 12` (the 32K preset):

| Depth | Prompt tok/s | Gen tok/s |
|---|---|---|
| 0 | 1608.2 | 42.2 |
| 8K | 562.9 | 39.3 |
| 16K | 338.8 | 35.7 |
| 32K | 190.2 | **29.5** |

Generation decay is **1.43x** — the exact same ratio as Qwen3.6 over the
identical range (31.8→22.2, also 1.43x). **Prompt decay is not** — 1608→190
is **8.5x**, far steeper than Qwen3.8's 2.4x over the same 32K range. This is
the one clearly worse number for GLM against everything else in this file: a
long system prompt or deep conversation history costs prompt throughput here
in a way it doesn't for the hybrid-attention Qwen models. Worth weighing for
agentic use, where most of the token cost is prompt, not generation.

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

> **All probe scripts and their raw per-model output now live in
> [`benchmarks/`](benchmarks/)** — one folder per model, generated by
> `benchmarks/run-suite.sh` rather than assembled by hand. This file holds the
> conclusions; that folder holds the evidence.

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

**Qwen3.5-27B-Uncensored, `--no-think`, 32K preset (q8_0 KV):** needle 5/5 at
31,596 tokens and semantic 5/5 at 28,149 tokens. Cached follow-ups 2.4-3.7s,
matching its Qwen3.8 twin's 2.5-3.2s. Only the 32K preset was probed, since
that is the only context this model has real headroom at.

This is the most direct evidence available against the model card's "zero
capability loss" claim, and it is consistent with it — an uncensored fine-tune
that had damaged retrieval would be expected to drop near-miss distractors
first, and it drops none. It is not proof: the clean control is stock
Qwen3.5-27B, which is not on disk, so this compares against a *newer* base
(Qwen3.8) and cannot separate the fine-tune from the version gap. The ~7%
generation deficit against Qwen3.8 is a version-and-quant difference, not
measured evidence of uncensoring cost.

**Qwen3.5-9B-Uncensored, `--no-think`, 256K preset (q8_0 KV, native max):**
needle 5/5 at 216,208 tokens and semantic 5/5 at 225,148 tokens — deep into
the native window, not a shallow spot-check, and the first time either recall
test has run against this card's true context ceiling on a dense model rather
than a VRAM-capped one. No OOM under either real haystack. Same reasoning
applies to its "zero capability loss" claim as the 27B above: consistent with
it, not proof of it, same missing stock-model control.

**The card's headline claim — "0/465 refusals" — is untested here and was not
attempted.** Every axis in this file is throughput, fit, recall, tool calling
or code quality; none of them require eliciting the content that claim is
about. Treat the refusal number as the vendor's, unverified.

**GLM-4.7-Flash, `--no-think`, 32K preset (`-ncmoe 12`, q8_0 KV):** needle 5/5
at 29,817 tokens and semantic 5/5 at 27,185 tokens. First recall data in this
file for an MLA-attention model — clean on both, no distinction from the
GQA/hybrid-attention models tested so far.

Both scripts take `--depth N` against any running server:

```bash
benchmarks/semantic-recall-test.py --depth 200000
```

**`semantic-recall-test.py` overshoots `--depth`.** It plants a distractor for
every target on top of the haystack, so the built prompt runs ~17% over the
requested figure — `--depth 30000` produced a 35,180-token request and a
flat HTTP 400 against a 32,768 window. Ask for roughly 80% of your context.

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
benchmarks/needle-test.py --depth 119000 --no-think
benchmarks/semantic-recall-test.py --depth 20000 --no-think
```

This also keeps the comparison fair: every long-context number already in this
file was measured on Qwen3-Coder-Next, which does not think at all.

### Both probes overshoot `--depth`, by different amounts

Neither script hits the depth you ask for, and the error is large enough to
push a request past `n_ctx` and get a bare `HTTP 400` back:

| Script | Asked | Built | Overshoot |
|---|---|---|---|
| `semantic-recall-test.py` | 30,000 | ~35,000 | **~17%** (adds a distractor per target) |
| `needle-test.py` | 185,000 | 199,478 | **~7.8%** |

Ask for roughly **80%** of the window on the semantic probe and **90%** on the
needle probe. A 199,478-token haystack against a 196,608 window fails with
`request (199478 tokens) exceeds the available context size` in the server log
and a naked `HTTPError: 400` at the client, which looks like a broken server
rather than a too-big prompt.

## Coding quality: executed, not read

`code-quality-test.py` scores a model by *running* its output. Seven tasks, each
asking for a from-scratch reimplementation of a stdlib behaviour; the checks
compare the model's function against the real one over edge cases plus a seeded
random batch. 50 checks total.

**The first version of this suite was worthless and the reason is worth
keeping.** It used self-contained leetcode-style tasks (merge intervals, LRU,
roman numerals) and every model scored **50/50**. Saturated, exactly like the
needle probes at 32K. Differential testing against stdlib is what produced
resolution: matching `urljoin` or `shlex.split` *exactly* is hard, matching them
on the happy path is easy, and the gap between those is the score.

The suite is validated against stdlib wrappers as reference solutions — all 7
tasks score 50/50 when the "model" is the real function, so a failure is the
model's, not the harness's.

| Model | BPW | Checks | Fully-clean tasks |
|---|---|---|---|
| Qwen3.8-27B `UD-IQ3_XXS` v3 | 3.148 | **38/50 (76%)** | 3/7 |
| Qwen3.8-27B `UD-Q3_K_XL` v3 | 3.802 | 35/50 (70%) | 2/7 |
| Qwen3-Coder-Next `UD-Q4_K_M` | ~4.5 | 34/50 (68%) | 2/7 |
| Qwen3.8-27B `UD-Q3_K_XL` **v2** | 3.932 | 33/50 (66%) | 2/7 |
| Qwen3.8-27B `UD-IQ4_XS` v3 | 4.131 | 30/50 (60%) | 2/7 |
| Laguna XS 2.1 `Q4_K_M` | ~4.5 | 27/50 (54%) | 1/7 |
| Laguna XS 2.1 `Q8_0` | ~8.5 | 27/50 (54%) | 2/7 |

**BPW does not order this table.** The highest-bit quant scores lowest and the
lowest-bit quant scores highest. IQ4_XS lost 9 checks in one go by emitting
Python that does not parse (`urljoin`, `SyntaxError`), which is a generation
failure rather than a knowledge one — but that is exactly the kind of failure
that matters in an agentic loop, so it is scored, not excused.

**Laguna XS 2.1 is the only model below the band.** 27/50 is 3 checks under the
previous floor. At `Q4_K_M`, 6 of those losses come from one task
(`add_months`) whose output **did not parse** — `SyntaxError: did you forget
parentheses around the comprehension target?`.

**Re-run at `Q8_0` it scores 27/50 again — and that is not the stability it
looks like.** The totals match; the distribution does not. Twenty of the fifty
checks changed hands, ten each way, netting exactly zero:

| Task | Q4_K_M | Q8_0 | |
|---|---|---|---|
| `glob_match` | 4/8 | 4/8 | |
| `shlex_split` | 4/7 | 2/7 | −2 |
| `urljoin` | 3/9 | 6/9 | +3 |
| `textwrap` | 4/6 | 3/6 | −1 |
| `csv_rows` | **7/7** | **0/7** | −7 |
| `add_months` | **0/6** | **6/6** | +6 |
| `parse_qsl` | 5/7 | 6/7 | +1 |
| **total** | **27/50** | **27/50** | **0** |

Two things follow. First, **the `SyntaxError` was a quantisation artifact, not
a property of the model** — at full precision `add_months` is one of only two
clean tasks. The earlier framing here, that an invalid-Python emit had decided
a row for the second time, was true of the Q4_K_M run but should not be read
as a Laguna trait. Second, and cutting the other way, `csv_rows` went from
7/7 to 0/7 at the *higher* quant, with all seven checks failing on code that
ran but returned the wrong thing — so near-lossless weights broke a task the
lossy ones aced.

**The honest reading is that 54% is the model.** Q8_0 is close enough to
ground truth that an aggregate this stable rules out quantisation as the
explanation for Laguna's floor. But per-task the instrument is noisy enough
that no single task's score should be quoted on its own, which sharpens the
"contribute noise rather than signal" caveat below into something measured
rather than suspected.

**v3 beats v2 at the same quant tier, 35 vs 33.** That is the only
same-tier-same-model comparison available here and it points the way Unsloth
claims, but two checks is far too narrow to call it confirmation of ">10% top-1%
accuracy". Treat it as not-contradicted, not as evidence.

`temperature 0.0`, and **the scores are exactly reproducible** — re-running
Q3_K_XL and Qwen3-Coder-Next returned 35/50 and 34/50 again, check for check.
Greedy decoding is deterministic here, so these are stable measurements rather
than single samples.

**Two findings:**

1. **The 80B coding specialist does not lead.** Qwen3-Coder-Next scores below
   both Qwen3.8-27B v3 quants that ran cleanly. Together with the CDN tie
   above, no axis measured in this repo shows it ahead. It is also the slowest
   generator of the five at 24.69 tok/s, against 29-30 for the dense 27Bs.
2. **Dropping to IQ3_XXS does not cost coding quality.** 3.148 BPW scored
   *above* 3.802. This is not evidence that fewer bits are better — it is
   evidence that at this spread, quant tier is not the dominant variable. It
   matters because it removes the open risk on the 192K preset: that config
   buys 64K of context without silently paying for it in code quality.

**What limits this.** The gap is 4 checks in 50 and all three sit in a 68-76%
band. They also fail on the *same* things — `urljoin` dot-segment removal (1-3
of 9 for every model), `textwrap` whitespace collapsing, `shlex` double-quote
escapes, `glob` `[]]` handling. Those tasks are near-floor for all three and
contribute noise rather than signal. A different task selection could reorder
the top two; it would be unlikely to promote Qwen3-Coder-Next past both.

> **Superseded on the quant question, 2026-08-21.** The two conclusions above
> that rank *quant tiers* — "dropping to IQ3_XXS does not cost coding quality"
> and "BPW does not order this table" — did not survive a more sensitive
> instrument. KL-divergence against BF16 orders the quants cleanly and
> monotonically by BPW, and puts IQ4_XS **3.3x closer** to the unquantised
> model than IQ3_XXS, the reverse of the check counts. See the next section.
> The *model* comparison (Qwen3-Coder-Next not leading) is untouched by this —
> KLD cannot compare different models, only a quant against its own reference.

## Quantisation fidelity: KL-divergence against BF16

`code-quality-test.py` resolves 4 checks in 50 across a 68-76% band. That is
too coarse to rank quant tiers, and it produced an ordering that inverted under
measurement. KLD is the right instrument for this specific question: it asks
how far a quantised model's output *distribution* has moved from the
unquantised one, per token, with error bars — no task design, no scoring
rubric, nothing to saturate.

**Method.** `benchmarks/kld-test.sh`. Reference is `unsloth/Qwen3.8-27B-GGUF`
**BF16**, 54.66 GB across two shards, sha256-verified against the HF LFS oids.
Corpus is wikitext-2 `wiki.test.raw`, the llama.cpp convention, so these
numbers are comparable to published KLD figures. `-c 512 --chunks 200` =
102,400 tokens prefilled, **51,000 scored** (llama.cpp scores the second half
of each window). The base logits file is 25.33 GB and was generated **CPU-only
in 16m49s** — BF16 does not fit in 16 GB, and running it on CPU also kept the
router usable throughout.

| Quant | BPW | Mean KLD | 99th-pct KLD | RMS Δp | Same top-1 |
|---|---|---|---|---|---|
| `UD-IQ3_XXS` v3 | 3.148 | 0.0589 ± 0.0007 | 0.577 | 6.88 % | 89.28 ± 0.14 % |
| `UD-Q3_K_XL` **v2** | 3.932 | 0.0299 ± 0.0004 | 0.345 | 5.05 % | 92.56 ± 0.12 % |
| `UD-Q3_K_XL` **v3** | 3.802 | 0.0263 ± 0.0003 | 0.276 | 4.61 % | 92.94 ± 0.11 % |
| `UD-IQ4_XS` v3 | 4.131 | 0.0179 ± 0.0002 | 0.189 | 3.80 % | 94.08 ± 0.10 % |
| **`UD-Q6_K` v3** | 6.431 | **0.0020 ± 0.00005** | 0.020 | 1.25 % | **97.96 ± 0.06 %** |

`Same top-1` is the fraction of scored tokens where the quant's argmax matches
BF16's. BPW is all tensors excluding the unused `blk.64` MTP head, computed
with `gguf-py` — the same convention that reproduces the figures elsewhere in
this file to within 0.003.

**BPW orders quality, and `code-quality-test.py` was measuring noise.** Every
gap in the table is 20-80 sigma. The check-count probe had IQ3_XXS at 38/50
beating IQ4_XS at 30/50; KLD puts IQ4_XS at a third of IQ3_XXS's divergence.
Both probes are internally reproducible — the difference is resolution, and a
50-point scale with shared near-floor tasks cannot see a 0.04 KLD gap.

**Q6_K is a different regime, not one more step.** 0.0020 against Q3_K_XL v3's
0.0263 is **13x** lower divergence, and top-1 disagreement falls from 7.1% to
2.0%. Nothing else in the table moves by that much for one tier.

**Unsloth Dynamic 3.0 is confirmed — by a stronger argument than the headline
number.** v3 beats v2 at the same nominal tier (0.0263 vs 0.0299, 12% lower
KLD) *while spending fewer bits*: 3.802 BPW against 3.932. Better fidelity from
a smaller file is a real recipe improvement, not a size-for-quality trade.

**But the vendor's ">10% top-1%" claim does not reproduce at this tier.** Top-1
agreement goes 92.559% -> 92.939%, i.e. disagreement 7.441% -> 7.061%. That is
+0.38 percentage points, or a **5.1% relative** reduction in disagreement —
about half the claim under the reading most favourable to it, and far off it
under the literal reading. Measured on one tier of one model against wikitext;
it is not a refutation of the claim in general, but it is not support either.

**The instrument was validated three ways**, because a number this clean
invites the suspicion that it is measuring the harness:

* **Self-KLD is zero.** A model scored against its own base gives
  KLD 4x10^-5 and Same-top-1 100.000% — float noise, as it must be.
* **Backend is not a confound.** The base is computed on CPU while the quants
  are scored on GPU, so some of the signal could have been CPU-vs-ROCm
  arithmetic. Scoring **BF16 itself** through the GPU path against the CPU base
  gives KLD **0.00000**, worst single token **0.000068**, and Same-top-1
  **100.000%** — the worst case is 30x smaller than Q6_K's *mean* of
  2.0x10^-3. The measured divergence is quantisation, not backend arithmetic.
  Raw output: `benchmarks/qwen3.8-27B-BF16-control/kld.txt`.
* **Mismatched runs cannot be compared by accident.** `kld-test.sh score` reads
  `-c` and `--chunks` back out of the base file header and refuses to run on a
  mismatch, so the one error that would silently produce garbage is blocked.

### IQ4_XS is a strict upgrade over Q3_K_XL at 32K

Measured 2026-08-21 after the KLD result, because KLD put `UD-IQ4_XS` 32%
closer to BF16 than `UD-Q3_K_XL-v3` while still fitting entirely on the card.
Both probes below ran back-to-back in one session with identical flags
(`-ngl 99 -c 32768 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0`).

| | `UD-Q3_K_XL` v3 | **`UD-IQ4_XS` v3** |
|---|---|---|
| Generation, n=3 | 29.70 ± 0.06 tok/s | **30.27 ± 0.014 tok/s** |
| Mean KLD | 0.0263 | **0.0179** |
| Same top-1 | 92.94 % | **94.08 %** |
| VRAM at 32K | 14,280 MiB | 15,343 MiB |
| Free | ~2,000 MiB | 955 MiB |

**It is better on both axes at once** — 32% lower divergence *and* 1.9% faster,
despite the file being 1.06 GB larger. The control reproduced 29.70 against the
29.67 already recorded for this preset, so the two sessions are comparable.

**Why the bigger file is faster is already in this file.** Dynamic 3.0 spends
**fourteen** distinct ggml quant types against v2's five, and that was measured
costing 3.6% of generation (30.78 -> 29.67). IQ4_XS has fewer dequant paths.
So `UD-Q3_K_XL-v3` pays a dequant tax for a quant that is *also* less faithful
than the one that does not pay it.

**The cost is headroom, not speed.** 955 MiB free against ~2,000 — still far
above the 281 MiB line this file already flags as too thin, but less room for a
second GPU consumer. f16 KV at 32K also fits (197 MiB free, GTT +6) and is
**not** recommended for exactly that reason.

Fit rows in `benchmarks/qwen3.8-27B-UD-IQ4_XS-v3/fit.txt`.

### What Q6_K costs to actually serve

The fidelity gain is real, and so is the bill. Q6_K's weights are **20,965 MiB
against 16,304 MiB of VRAM**, so unlike every other config in this file it
*cannot* run fully offloaded — `-ngl` becomes the variable, and the remainder
sits in DDR4.

| `-ngl` | 32K, f16 KV | free at load | GTT |
|---|---|---|---|
| 44 | **SPILL** | 24 MiB | **+1,623 MiB** |
| **42** | fits | **495 MiB** | +6 MiB |
| 40 | fits | 1,123 MiB | +6 MiB |
| 38 | fits | 1,833 MiB | +6 MiB |

**`-ngl 44` is the exact failure the spill guard was added for.** Its `peak` of
16,244 reads as a 60 MiB fit; VRAM at load was 16,280 with 24 free and GTT rose
1,623 MiB. Without the guard this row would have gone into the table as a pass.

At `-ngl 42`, 32K, f16 KV, measured with the standard 700-token probe at
temperature 0.0, n=3:

| | Q3_K_XL v3, `-ngl 99` | **Q6_K v3, `-ngl 42`** |
|---|---|---|
| Generation | 29.67 tok/s | **4.24 ± 0.005 tok/s** |
| Prefill (batch 2048) | 1,164 tok/s | **470 tok/s** |
| Mean KLD | 0.0263 | 0.0020 |
| Same top-1 | 92.94 % | 97.96 % |

**So the trade is 7x generation and 2.5x prefill for 13x lower divergence.**
The three runs returned 4.25 / 4.24 / 4.24 — this is a measurement, not a
sample. At 4.24 tok/s a 700-token answer takes 165 s, which puts Q6_K firmly in
batch-and-come-back territory rather than interactive or agentic use. That is
the honest shape of "highest quality practically" on this card: the quality is
available, but not at a speed that survives a Cline loop.

Note also that **f16 KV is affordable here and is not elsewhere.** Offloading
22 layers to DDR4 frees enough VRAM that full-precision KV at 32K costs
nothing extra — the constraint moved from the cache to the weights.

**What this does not say.** KLD compares a quant against *its own* unquantised
weights, so it cannot rank different models — Qwen3.8 against Qwen3-Coder-Next
is still a question for the task probes. It is measured on wikitext, which is
prose; a code corpus could shift the ordering, and the base pass would have to
be regenerated to find out. And low divergence from BF16 is not the same as
being *good* — it means faithful to the original model, whatever that model is
worth.

## Knowledge freshness: measurable, and it did not separate the models

`cdn-freshness-test.py` is the `recharts_test.py` idea generalised: ask for a
self-contained browser page, regex every `src`/`href`, HEAD each URL, count
what resolves. No judgement calls. A model with stale library knowledge reaches
for CDN paths that have since moved or never existed — the same failure behind
the Recharts and MUI UMD gotchas that trip every model on this box.

Three prompts (Recharts, MUI, Chart.js + D3), 3 runs each, `temperature 0.0`:

| Model | Released | URLs resolve | Fully clean runs |
|---|---|---|---|
| Qwen3.8-27B `UD-IQ3_XXS` v3 | 2026-08-05 | **36/39 (92%)** | 6/9 |
| Qwen3-Coder-Next `UD-Q4_K_M` | 2026-01-30 | **39/42 (93%)** | 6/9 |
| Laguna XS 2.1 `Q8_0` | 2026-07-21 | 27/36 (75%) | 3/9 |
| Laguna XS 2.1 `Q4_K_M` | 2026-07-21 | 18/36 (50%) | 3/9 |

**A tie between the first two, and that was the original finding.** Six months
of release-date gap produced no measurable difference on this axis. Each model
fails deterministically on one library and gets the other's right:

* Qwen3.8 always emits `unpkg.com/@mui/material@5/dist/material-ui.production.min.js` — dead.
* Qwen3-Coder-Next always emits `unpkg.com/recharts@2.10.0/umd/recharts.min.js` — dead, and it is the exact "Recharts ships no `.min` UMD build" trap already documented in the session notes.

So "the coder model's knowledge is outdated" is **not reproduced** by this
probe. Either the perception comes from a different axis — library *API*
surface rather than *distribution* paths — or it is real and this probe is the
wrong instrument. Worth knowing before choosing a model on freshness grounds.

**Laguna XS 2.1 does separate, 2026-08-23 — so the probe was not saturated.**
The "everything ties at ~92%" reading held only while every model tested was a
Qwen. Laguna is the newest model in the table by release date and the worst on
it, so recency does not predict this score either.

**But most of that gap was the quant, not the lab — and this is the one probe
here that is sensitive to quant tier.** Re-running Laguna at `Q8_0`, which is
effectively lossless, moved it from 18/36 to **27/36**, recovering 9 URLs:

| | Q4_K_M | Q8_0 |
|---|---|---|
| URLs resolve | 18/36 (50%) | **27/36 (75%)** |
| distinct dead paths | 6 | 3 |

Q4_K_M invents `@emotion/react`, `@emotion/styled` and `prop-types` script
tags that Q8_0 simply does not emit. What survives at Q8_0 is the *same* two
traps every model on this box hits — the Recharts UMD path and the MUI UMD
paths — so at full precision Laguna fails like its peers rather than uniquely.

This matters beyond Laguna. `code-quality-test.py` scored **27/50 at both
quant tiers**, while this probe moved 25 points on the same two files. Recall
of specific version strings and CDN paths degrades under quantisation well
before procedural coding ability does, which is consistent with the KLD
result — and it means a knowledge probe is the cheaper instrument for
detecting quant damage than a coding probe. Treat the cross-lab spread in the
table above as an upper bound: some of every gap there is quantisation.

Release dates for everything on disk, since it bounds the cutoff even if it
does not equal it:

| Model | HF release |
|---|---|
| Qwen3.8-27B | 2026-08-05 |
| Qwen3.6-35B-A3B | 2026-04-15 |
| Gemma 4-26B-A4B | 2026-03-11 |
| Qwen3-Coder-Next | 2026-01-30 |
| GLM-4.7-Flash | 2026-01-19 |
| GPT-OSS-20B | 2025-08-04 |

One measured aside: Qwen3-Coder-Next took **202s** to become ready from cold on
the BX500 today, against the ~93s recorded earlier in this file. Same binary,
same `-ncmoe 38`. Cold-load cost on this SATA drive is not a stable number.

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

#### Q8_0 does not buy code quality — tested directly

The obvious next question is whether quantisation was the real limit all
along. It is not, and the test was unambiguous.

Qwen3-Coder-30B-A3B at **Q8_0** (near-lossless) against Qwen3-Coder-Next at
**Q4_K_M** — same family, same specialisation, both ~3B active, so the
comparison isolates *size versus precision*:

| Model | Quant | Scripts resolving | React API | Recharts `layout` | Data sorted |
|---|---|---|---|---|---|
| Devstral Small 2 24B | Q4_K_M | 3/4 | `createRoot` ✓ | `vertical` ✓ | ✓ |
| Qwen3-Coder-Next 80B/3B | Q4_K_M | 2/4 | `createRoot` ✓ | `vertical` ✓ | ✓ |
| **Qwen3-Coder-30B/3B** | **Q8_0** | **0/1** | `render` ✗ (React 17) | `horizontal` ✗ | ✗ |

The Q8_0 model emitted a **single** script tag — no React, no ReactDOM, no
Babel — then called `ReactDOM.render` on globals that were never loaded, wrote
JSX into a plain `<script>` block with no transform, and listed data as
`88, 91, 72, 77, 65` under a comment claiming it was sorted highest-first.
Consistent across three runs at `temperature 0.3`.

**Near-lossless precision on a smaller model lost decisively to 4-bit on
bigger ones.** It failed on things the Q4 models got right — the React 18 API,
the Recharts layout idiom — which are knowledge questions, not precision ones.

It was also slower. `-ncmoe 30`, q8_0 KV:

| Depth | 30B Q8_0 | Qwen3-Coder-Next Q4_K_M |
|---|---|---|
| 0 | 23.5 tok/s / 1315 pp | ~25 / ~700 |
| 8K | 20.5 | — |
| 32K | **15.9** | ~24 @23K, 22.6 @47K |

Two structural reasons: Q8_0 weights are ~2x the bytes of Q4_K_M, so with 30
expert layers streaming from DDR4 at ~40 GB/s the effective throughput roughly
halves; and its KV is **52,224 B/token** against Coder-Next's 13,056, four
times the cache to read per generated token.

**So Q4_K_M is not what limits coding here.** That also retires the suspicion
hanging over Qwen3.8 at Q3_K_XL being unfairly handicapped — Q3 remains a
legitimate concern, Q4 does not. Total parameters and model recency dominate
precision at these bitrates.

Verified against its own GGUF while testing: 48 layers, 4 KV heads x 128 =
52,224 B/token, i.e. ~52 GB at 1M. The estimate stated earlier in this file
for this model was right.

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

#### Making the model verify its own dependencies fixes it

Both failure classes above are addressable from the prompt, but differently.
Geometry errors are not fixable by giving information; **dependency errors
are**, and the model can be made to find them itself rather than being told.

Adding a verification phase — *fetch each script URL and confirm HTTP 200
before writing it; do not guess filenames or assume a `.min` build exists;
read the library's own browser/UMD docs for peer dependencies that must be
globals first* — produced the first unambiguous success:

| Attempt | Library | Scripts resolving | Peer deps found |
|---|---|---|---|
| Qwen3-Coder-Next | Recharts | 2/4 | ✗ |
| Devstral Small 2 | Recharts | 3/4 | ✗ |
| Qwen3-Coder-30B Q8_0 | Recharts | 0/1 | ✗ |
| **Gemma 4 + verify phase** | **MUI** | **6/6** | **✓** |

Gemma 4 loaded React, ReactDOM, Babel, `@mui/material`, **and both
`@emotion/react` and `@emotion/styled`** — MUI v5's styling engine, which is
its equivalent of the `prop-types` trap nobody found on Recharts. It reported
an HTTP status for each; all six were independently re-checked here and all
six genuinely return 200. It also took the date from a `get_current_timestamp`
tool call rather than guessing, fixing the wrong-date error seen earlier.

**Two variables changed at once** — the library and the prompt — so this does
not isolate which mattered. But volunteering "@emotion is required by MUI v5"
is not something library popularity alone explains; that reads like the
instruction to go read the browser-usage docs doing the work.

Practical rule: **make the model verify, do not make it guess.** Requiring an
observed HTTP status per URL turns a silent 404 into something it has to
notice and fix before writing the file.

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
| Qwen3.8-27B `UD-Q3_K_XL` **v3** @32K | ✓ `PROBE-770487` | ✓ sum `1,355,528` | same three-call delegation as v2; comma-formats the sum where v2 did not |
| Qwen3.8-27B `UD-IQ4_XS` v3 @32K | ✓ `PROBE-770487` | ✓ sum `1,355,528` | same three-call delegation |
| Qwen3.8-27B `UD-IQ3_XXS` v3 @192K | ✓ `PROBE-770487` | ✓ sum `1,355,528` | same three-call delegation — structured output survives 3.148 BPW |
| Qwen3.5-27B-Uncensored @32K | ✓ `PROBE-770487` | ✓ sum `1355528` | three calls — also delegated the addition to `add_numbers`, same as its Qwen3.8 twin |
| Qwen3.5-9B-Uncensored @256K | ✓ `PROBE-770487` | ✓ sum `1,355,528` | three calls, same delegation pattern; wrote the sum comma-formatted, which is numerically identical but broke a naive exact-match probe — worth knowing if you script against this model |
| GLM-4.7-Flash @32K | ✓ `PROBE-770487` | ✓ sum `1,355,528` | same delegation pattern, same comma-formatting; tested at general-use sampling params, not the vendor's tool-calling-specific ones (see config section) |

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

### It recurs per model — GPT-OSS-20B in Cline, 2026-08-17

The `peg-native` parser derives a grammar from each model's chat template, so
it breaks **per model** and gets fixed per model. Driving `gpt-oss-20b`
agentically through Cline fails with:

```
The model produced output that does not match the expected peg-native format
```

Independently corroborated by other users, so it is not a local
misconfiguration. Two things narrow it usefully:

* **A single-turn tool call through the API works fine** — correct
  `tool_calls`, HTTP 200. So neither the model nor the parser is broken in
  general; it is specific to how Cline drives it (large system prompt, many
  tools, multi-turn history, GPT-OSS's analysis channel preceding the call).
* **Updating does not fix it.** `7c35571e5` is 99 commits past the previous
  build and contains two adjacent per-model tool-call fixes — `chat : fix LFM2
  tool call arg name prefix ambiguity` and `chat : fix muse-glimmer detection
  of tool calls after EOM` — but nothing for GPT-OSS. Its turn has not come.

Record it as a **harness limitation, not a model limitation**. "GPT-OSS cannot
do the task" is the wrong note; "GPT-OSS cannot currently be driven agentically
through llama.cpp's peg-native parser" is the right one.

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
build** — `build/` for everything since Vulkan was retired. This
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
gpt-oss-20b at 32k used to give up Vulkan's 181 vs 148 tok/s — no longer true
since Vulkan was retired, so router and pinned mode are now equivalent. Formerly:
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
| Qwen3.8-27B | 27B | 27B | Dense hybrid, 64L | UD-Q3_K_XL (**Dynamic 2.0**) | 12.5GB | yes |
| Qwen3.8-27B | 27B | 27B | Dense hybrid, 64L | UD-Q3_K_XL (**Dynamic 3.0**) | 12.2GB | yes |
| Qwen3.8-27B | 27B | 27B | Dense hybrid, 64L | UD-IQ4_XS (Dynamic 3.0) | 13.3GB | yes |
| Qwen3.8-27B | 27B | 27B | Dense hybrid, 64L | UD-IQ3_XXS (Dynamic 3.0) | 10.2GB | yes |
| Nemotron-3-Nano-30B-A3B | 31.6B | ~3.5B | MoE Mamba2 hybrid, 52L | UD-Q4_K_XL | 22.8GB | deleted |
| Devstral Small 2 24B | 23.6B | 23.6B | Dense, full attn, 40L | Q4_K_M | 14.3GB | deleted |
| Qwen3-Coder-30B-A3B | 30.5B | ~3B | MoE, full attn, 48L | Q8_0 | 32.5GB | deleted |
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

## TurboQuant: 2-4 bit KV cache (experimental, not a preset)

**Tested and rejected — keep `Q3_K_XL` + `q4_0` at 128k.** TurboQuant's
Walsh-Hadamard-rotated KV types compress the cache far past `q4_0` and really do
change what fits: `Qwen3.8-27B-UD-IQ4_XS-v3` runs at **131,072** with `turbo2`
and `-ub 256`, where the same model with `q4_0` cannot even allocate its compute
buffers. It passes 5/5 needle and 5/5 semantic at ~121k.

It is still the wrong trade, and only KL-divergence shows why:

| KV cache | Mean KLD vs f16 |
|---|---|
| `q8_0` | 0.000744 |
| `q4_0` | 0.003901 |
| `turbo3` | 0.009823 |
| `turbo2` | **0.030743** |

`turbo2`'s **cache** costs more distribution quality (0.0307 / 92.34% top-1)
than this model's entire **weight** quantization does (`Q3_K_XL-v3`: 0.0263 /
92.94%). Even granting `IQ4_XS` a perfect weight cost, the combination loses to
what is already running. Both retrieval tests scored 5/5 on the rejected config
and were blind to a 7.9x divergence gap — **needle and semantic recall are
regression alarms, not quality instruments.**

It is also **not merged into llama.cpp** and runs only from a fork, so nothing
is wired into `switch-model.sh`. [`turboquant.md`](turboquant.md) has the full
record — the build, the RDNA4 confirmation, an environment variable that
silently overrides `-ctk`, three harness faults that make **any**
`needle-test.py` run against a Qwen3.8 preset score 1/5 for reasons unrelated to
the KV cache, a retracted 262,144 claim that allocated cleanly and would have
died on the first real prompt, and one genuinely free finding: **`gemma4:32k`
ships `-ncmoe 8` but runs +14% prompt / +12% generation at `-ncmoe 4` on stock
`q8_0`**, no fork required.

---

## Real-world testing

Throughput, VRAM and recall are here. Whether the models can actually **do a
job** — research live data, build something, find their own bugs — is in
[`real-world-testing.md`](real-world-testing.md), covering agentic runs through
Cline against this router.

Its headline: the same models that produced four undetected blank pages in Open
WebUI catch their own 404s once given a browser console. The bottleneck was the
absence of a feedback loop, not model capability.

## Claude Code against this router

Open WebUI is not the only client. Claude Code runs against these presets too —
over the LAN, with tool calling, `WebFetch` and Chrome DevTools — and
[`claude-harness.md`](claude-harness.md) documents what it takes.

The part that needed no work: llama.cpp serves the **Anthropic** Messages API
natively (`/v1/messages`), so no translation proxy is involved. The part that
did: four separate things must be right, and each fails with an error that does
not name its cause — a **41,796-token** system prompt that no 32k preset can
answer, three claude.ai Notion tool schemas that crash llama.cpp's JSON-schema
to GBNF converter and take *all* tool calling with them, four model slots where
setting only `ANTHROPIC_MODEL` leaves three pointing at real Anthropic names,
and a single screenshot that 500s a text-only backend into a retry loop.

`claude-local.sh` is the client-side launcher that encodes all four:

```bash
claude-local list                        # what the router is serving
claude-local qwen3-coder-80B-A3B-128k    # switch model
claude-local --chrome                    # add Chrome DevTools, text-only tools
```

## aider against this router

A third harness, and the opposite trade-off from Claude Code's:
[`aider-harness.md`](aider-harness.md) covers it. aider parses plain-text
diffs and plain-text shell-command suggestions instead of native tool-calling,
so it sidesteps every model this router disqualifies elsewhere —
**11 of 11 presets work**, including `qwen3.8-27B` (blocked under Claude Code
by a chat-template message-ordering conflict) and `gpt-oss-20b` (blocked
under both Cline and Claude Code by parser/grammar failures).

That compatibility comes at a cost only visible once a real multi-step task
runs through it end to end. `--yes-always` deliberately does not approve
shell command execution — a model that writes a research script and correctly
says "I can't run this" is not confused, it is describing a genuine
confirmation gate the flag does not cover. A non-Playwright `/web` scrape can
balloon to millions of tokens with no compaction to recover. A model's default
`edit_format` can misread its own correctly-formatted shell command as a
malformed file edit. Two of the four have real CLI flags and are handled by
[`aider-local.sh`](aider-local.sh) for everyday interactive use; the other
two only matter unattended (`--yes-always`, nobody approving prompts), and
[`aider-driver/`](aider-driver) — the reproducible driver behind the
write-up — is the template for that case.

## Open WebUI

The client this box is driven from, reachable at `http://192.168.4.228:8080`.
Reconstructed from the running container, not from upstream's example:

```bash
docker run -d --network=host \
  -v open-webui:/app/backend/data \
  -e OPENAI_API_BASE_URL=http://127.0.0.1:8090/v1 \
  -e OPENAI_API_KEY=local \
  -e ENABLE_OLLAMA_API=false \
  -e WEBUI_SECRET_KEY="$(cat ~/.owui_secret_key)" \
  --name open-webui \
  --restart always \
  ghcr.io/open-webui/open-webui:main
```

**`WEBUI_SECRET_KEY` must be pinned, or every update logs everyone out.**
`start.sh` auto-generates this key on first boot when the env var is unset,
and saves it to `/app/backend/.webui_secret_key` — **outside** the mounted
`/app/backend/data` volume (checked in the image's own `start.sh`, not
assumed). `docker rm` during an update destroys that file along with the
container's writable layer, so the next boot silently generates a *new*
random key. That key signs every login session, so a rotation force-logs
every user out — which looks exactly like "the update wiped my settings"
even though the database (chats, admin config, functions) is completely
untouched in the volume the whole time. Generate one once
(`openssl rand -base64 32 > ~/.owui_secret_key`) and pass it explicitly on
every `docker run`; the update procedure below already assumes this.

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
the container. Updating therefore does not lose any *data* — but note the
`WEBUI_SECRET_KEY` above: without it pinned, every update force-logs every
user out even though the volume is fine, which is easy to mistake for data
loss:

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

### HTTPS: Chrome specifically needs it, other browsers don't

Chrome gates several web APIs (service workers — Open WebUI is a PWA —
clipboard write, etc.) behind a "secure context" check, which requires
`https://` or `localhost` specifically. Plain `http://192.168.4.228:8080`
loads the page fine but fails that check, silently, in Chrome only — Firefox
and Safari are more lenient about non-HTTPS origins and do not show the
problem. A self-signed certificate genuinely fixes it: Chrome's
secure-context check only cares that the TLS handshake succeeded, not
whether the certificate is trusted, so clicking through the "not secure"
warning once is sufficient.

A Caddy reverse proxy in front of the existing container, not a change to
it:

```bash
mkdir -p ~/caddy
cat > ~/caddy/Caddyfile <<'EOF'
https://192.168.4.228:8443 {
    tls internal
    reverse_proxy localhost:8080
}
EOF

docker run -d --name open-webui-tls --restart unless-stopped --network=host \
  -v ~/caddy/Caddyfile:/etc/caddy/Caddyfile \
  -v caddy-data:/data \
  caddy:2-alpine

sudo ufw allow 8443/tcp   # new port -- 8090's rule does not cover it
```

**Skipping the `ufw` line fails from any other device with `ERR_ADDRESS_UNREACHABLE`**,
not a certificate warning — the container is genuinely fine (`curl -k
https://192.168.4.228:8443/` from the box itself returns 200) but the LAN
never reaches it. `8090`'s existing rule does not carry over; each port needs
its own `ufw allow`.

`tls internal` is Caddy's own local CA — it self-signs a leaf certificate
with no external dependency (no Let's Encrypt, no manual `openssl`). The leaf
cert is short-lived (~12h) by design and renews automatically in the
background as long as the container keeps running, which `--restart
unless-stopped` covers. `--network=host` for the same reason as the main
container: it needs to reach `open-webui` at `localhost:8080` without
Docker's bridge-network address translation getting in the way.

Open **`https://192.168.4.228:8443`** in Chrome, accept the certificate
warning once (`Advanced → Proceed`), and PWA-gated features that silently
failed over plain HTTP work from then on. To remove the warning entirely
rather than click through it, install Caddy's root CA
(`docker exec open-webui-tls cat /data/caddy/pki/authorities/local/root.crt`)
into the OS or browser trust store on each device that connects — optional,
and only worth doing if the warning itself is the annoyance rather than the
blocked APIs.

### Web search returns stale results, and no backend can fix it

**Symptom:** asked any model "what's the best X" for a fast-moving product
category with no year specified, it answered from an old, well-ranked "best
of"/buying-guide page — Canon DSLRs, specifically — without noticing the
product line it was describing had since been discontinued. Saying "this is
2026" got a better answer; saying it a second time ("X is too old") got the
actually-current one. Three-plus turns to get there is not acceptable for
something the model should get right on the first pass.

**Root cause, checked in `open_webui/retrieval/web/*.py` inside the
container, not assumed:** no search backend Open WebUI ships passes a
recency/date-range parameter — checked DuckDuckGo, Tavily, Brave, Serper and
Kagi. The DuckDuckGo case is sharpest: the underlying `ddgs` library supports
a `timelimit` argument (day/week/month/year), and Open WebUI's connector
simply never passes it —

```python
search_results = ddgs.text(query, safesearch='moderate', max_results=count, backend=backend or 'auto')
```

So switching search engine does not fix this; the gap is in Open WebUI's
integration layer, not any one provider.

**Two contributing bugs, both fixed, neither is the search backend:**

1. `Admin Panel → Settings → Interface → Query Generation Prompt` was empty
   (using the built-in default), which does inject `{{CURRENT_DATE}}` but
   buries it as one line inside a long JSON-formatting instruction block. The
   model that generates the search query is whatever chat model is
   active — confirmed via `task.model.default = ""` and `Local Task Model:
   Current Model` in the settings UI, so it is not a separate, weaker task
   model. Fix: override the template with the date moved to the first line
   and an explicit instruction to put the actual current year in the query
   text, since that — not date-unawareness — was the observed failure mode.
2. No global system prompt exists in this version of Open WebUI (checked all
   ~280 keys in the `config` table; nothing like it is there), and the
   per-model System Prompt field would mean setting it individually on every
   router preset. Fix: a **Global Filter function**
   (`openwebui-current-date-filter.py` in this repo) installed via
   `Admin Panel → Functions`, injecting a system note with the real date into
   every chat regardless of which model is selected.

**What actually closed the gap was a third change, once the first two proved
insufficient on their own:** the filter's note originally only asserted the
current date. That was not enough — the model already knew the date and
*still* took the stale buying-guide page at face value, because knowing the
date does not by itself make a model suspicious of specific content. v1.1 of
the filter adds an explicit instruction to treat "best/top/latest X" results
as potentially superseded and check for discontinuation before presenting
them as current. After that change, a bare prompt with no year and no
pushback returned the correct, fully-hedged 2026 answer in one turn — 14
searches and 8 fetches, up from 6 and 5, because it was now cross-referencing
rather than trusting the top hit.

**Not fixed, and not fixable by prompting:** `web.search.result_count` is 3
by default (bumping it to ~5 gives more chance a current source appears in
the mix, cheap insurance, not a fix). More fundamentally, no config change
gives the search layer itself a freshness signal — the model is still doing
all the recency judgement post-hoc, on ordinary-looking content, with a
27B-class local model's reliability at that judgement call. Treat this as a
standing limitation of the stack: for genuinely fast-moving categories,
occasional pushback should still be expected, not a sign the setup is broken.
