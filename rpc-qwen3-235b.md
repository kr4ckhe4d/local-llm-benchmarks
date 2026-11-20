# Qwen3-235B-A22B across two machines over llama.cpp RPC

Measured 2026-11-20. A 97 GiB model that fits neither box alone, run across this PC
(RX 9070 XT + R9700, 30 GB DDR5) and `ubuntulocal` (Arc B580, 60 GB DDR4) over a
direct 2.5 GbE cable, with llama.cpp's RPC backend.

**Result: it runs, at 5.5 tok/s generating and 77 tok/s reading a 512-token prompt**,
with 35 of its 94 layers in the server's DDR4. Usable for one-off questions, not for agents.
Getting there took two system freezes, both fixed: one from the client's own memory map,
one from the Radeon Vulkan driver spilling VRAM into system RAM. Both are written up below
because they will bite any large RPC load on this box.

## Setup

| | This PC (client) | ubuntulocal (`rpc-server`) |
|---|---|---|
| Devices | RX 9070 XT 16 GB (`ROCm0`), R9700 32 GB (`ROCm1`) | Arc B580 12 GB (`RPC0`), Ryzen 9 5950X + 60 GB DDR4-3200 (`RPC1`) |
| RAM | 30 GB DDR5-6000 (9800X3D) | 60 GB |
| llama.cpp | `b94959a64`, ROCm 7.2.4 + RPC, in a separate worktree (`~/llama-rpc`) | `b94959a64`, Vulkan + RPC (Mesa 26.0.8), `-d Vulkan0,CPU -t 16 -c` |
| Link | direct 2.5 GbE, 10.10.10.1 ↔ 10.10.10.2, ~0.2-0.45 ms RTT, ~280 MB/s | `rpc-server` bound to 10.10.10.2 only (RPC has no auth) |

Model: `unsloth/Qwen3-235B-A22B-Instruct-2507-GGUF` UD-Q3_K_XL, 3 shards, 96.99 GiB,
sha256-verified against Hugging Face. 94 layers, 128 experts, 8 active (22B active params).

Both ends must run the same llama.cpp commit: the RPC protocol is versioned.

Run: [`benchmarks/rpc-qwen3-235b.sh`](benchmarks/rpc-qwen3-235b.sh); layer splits from
[`benchmarks/rpc-split.py`](benchmarks/rpc-split.py), which reads each layer's real size from the
GGUF and fills devices in order to a GiB budget. `-fa 1 -lm none -ngl 99`, pp512 and tg128,
2 repetitions, empty context. Raw JSON and logs: [benchmarks/raw/rpc-qwen3-235b/](benchmarks/raw/rpc-qwen3-235b/).

## Results

| Config | 9070 XT | R9700 | B580 | Server RAM | This PC's RAM | pp512 | tg128 |
|---|---:|---:|---:|---:|---:|---:|---:|
| A: GPU budgets 12 / 24 GiB | 11 layers | 23 | 8 | 52 (53.8 GiB) | — | 55.2 ± 0.3 | 4.71 ± 0.02 |
| A2: GPU budgets 13.5 / 29.5 GiB | 13 | 28 | 8 | 45 | — | 63.7 ± 0.2 | 5.18 ± 0.02 |
| **C: A2 + 10 layers' experts in local RAM** | 13 | 38 (10 attention-only) | 8 | 35 | ~10 GiB experts | **76.8 ± 0.3** | **5.53 ± 0.03** |

C puts layers 41-50 on the R9700 with their expert tensors overridden to the local CPU
(`-ot 'blk\.(4[1-9]|50)\.ffn_(up|down|gate)_exps\.weight=CPU'`), so attention for those layers
runs on the card and their experts on the 9800X3D's DDR5.

Each load took ~4.5-5.5 min (the server's share crosses the cable; `rpc-server -c` caches
tensors on the server's disk, so repeat loads send hashes instead).

### Where the time goes

Per generated token: A 212 ms, A2 193 ms, C 181 ms.

- A → A2 moves 7 layers from the server's DDR4 to the Radeons and saves 19 ms: **a layer on
  the server CPU costs at least ~2.7 ms per token**. At ~0.1 GB of active weights per layer
  (Q3_K_XL), that is ~36 GB/s, about what dual-channel DDR4-3200 delivers in practice.
- A2 → C moves 10 more layers off the server, their experts onto this PC's DDR5, and saves
  another 12 ms: a local-RAM layer costs ~1.5 ms less than a server one.
- With 35 layers left on the server, roughly 95 of the 181 ms is the 5950X reading DDR4.
  **The server's memory bandwidth is the ceiling.** More GPU on either side would not move it
  much; fewer layers on the server would.

Prompt reading is CPU-bound the same way: experts in RAM are computed by that machine's CPU
for every prompt token (op offload to the GPU applies to local host memory only, not to an
RPC CPU device).

### Is it worth it?

On this hardware, only for a model that is the point in itself. 5.5 tok/s is reading speed
for short answers; a 2,000-token answer is 6 minutes, and a 30K-token agent prompt at 77 tok/s
is 6.5 minutes before the first output token. For comparison on this site, models that fit
this PC alone (gpt-oss-120b at 59 GiB, Qwen3-Next-80B Q6) need no RPC and no second machine.

## Two freezes, and what fixed them

Both were global out-of-memory on this 30 GB PC that took down the desktop (KDE session
killed, `kwin_wayland` then also crashed on restart on an unrelated KWin 6.8.3 bug in
`syncTabletWithMouse` when the mouse moves during greeter start; `systemctl restart sddm`
without touching the mouse brought it back).

### 1. The client memory-maps the whole model (09:52)

With the default `-lm auto` the client mmaps every shard, all 97 GiB, including the 62 GiB
that only get sent to the server. Measured on gpt-oss-20b split with the server: peak
file-backed RSS 11.6 GiB (the whole file) with mmap, 0.07 GiB with `-lm none`, whose anonymous
peak is 0.7 GiB. At 97 GiB on a 30 GB box, reclaim did not keep up. **Use `-lm none` (or
`dio`) for any RPC load bigger than local RAM.**

### 2. Vulkan (RADV) evicts the R9700's VRAM into system RAM (10:05)

The client was first built with Vulkan because ROCm 10.1 (pulled in by a system update the
night before) crashed llama.cpp in `hipStreamCreateWithFlags` on every load, on both the
router's build and a fresh one. On Vulkan, with `-lm none` and the bench inside a 22 GB
cgroup, RAM still ran out, because the memory was the amdgpu driver's GTT (system RAM the GPU
maps), which no process cgroup counts. Each card may claim up to 15.2 GiB of GTT, half of
system RAM, so three cards can exhaust it alone.

A watchdog ([probe-watchdog.sh](benchmarks/raw/rpc-qwen3-235b/probes/probe-watchdog.sh)) that
traces per-card VRAM/GTT every 0.2 s and kills the bench under 8-10 GiB available caught it:
the 9070 XT loaded 12.8 GiB cleanly, then while the R9700's weights uploaded its VRAM drained
into GTT, from 29 GiB (first try) and again from 24 GiB of a 32 GiB card
([trace](benchmarks/raw/rpc-qwen3-235b/probes/vulkan-24gib-r9700-verbose.trace),
[log](benchmarks/raw/rpc-qwen3-235b/probes/vulkan-24gib-r9700-verbose.log)). It is not
plain VRAM exhaustion. Cause not pinned down beyond "RADV on Mesa 26.2.6 / kernel 7.3.4".

**Fix: ROCm rolled back to 7.2.4** (21 packages from the pacman cache, `rocm-llvm-libs`,
`rocm-openmp`, `amdsmi` removed, held with `IgnorePkg`). On ROCm the same 24 GiB R9700 load
stayed in VRAM with RAM flat at ~19 GiB available
([trace](benchmarks/raw/rpc-qwen3-235b/probes/rocm-24gib-r9700.trace)), and the router's
build went from 1-in-3 load crashes to 5 of 5 clean. The bench script keeps `-lm none`, the
22 GB scope and the watchdog anyway.

## Smaller findings on the way

Exploratory, read off the terminal, not saved as raw files:

- **SYCL behind RPC does not work for most quants.** The SYCL backend's reorder optimisation
  stores data in `tensor->extra`, which RPC rejects (`tensor->extra populated by the backend,
  this is currently unsupported`); gpt-oss-20b (MXFP4) failed to load on it. Q8_0 loaded but
  decoded at 10.4 tok/s on the B580 through RPC against 44.0 locally. The server runs the
  Vulkan build behind RPC instead.
- **RPC overhead per token is small on Vulkan.** Qwen3.5-9B Q8_0 split half R9700 / half
  B580: 17.1 tok/s (Vulkan `rpc-server`) against 15.1 (SYCL); the B580's own Vulkan Q8_0
  matvec is the slow half. gpt-oss-20b split R9700 / B580 (Vulkan): 35.7 tok/s; R9700 /
  server CPU: 21.4; R9700 alone: 182.
- The direct link is not the bottleneck: per-token traffic is a few KB of activations each way.

## Running it again

```sh
# server (ubuntulocal)
~/rpc-start-vk.sh            # ggml-rpc-server -H 10.10.10.2 -p 50053 -d Vulkan0,CPU -t 16 -c
# client (this PC), config C
HIP_VISIBLE_DEVICES=0,1 ~/llama-rpc/build/bin/llama-server \
  -m /mnt/fast/models/qwen3-235b/Qwen3-235B-A22B-Instruct-2507-UD-Q3_K_XL-00001-of-00003.gguf \
  --rpc 10.10.10.2:50053 -lm none -ngl 99 -fa on -dev ROCm0,ROCm1,RPC0,RPC1 -ts 13,38,8,35 \
  -ot 'blk\.(4[1-9]|50)\.ffn_(up|down|gate)_exps\.weight=CPU'
```

Only `llama-bench` was built in `~/llama-rpc/build`; build `llama-server` there first
(`cmake --build build --target llama-server`). Not tested as a server yet; longer contexts
need KV room the budgets above leave little of.

## Not done yet (paused 2026-11-20)

- **More of this PC's RAM.** C used ~10 GiB of DDR5 for experts; ~8 GiB more fits inside the
  watchdog's 8 GiB margin. At the measured ~1.2 ms saved per layer moved off the server, that
  is an estimated ~5.8-5.9 tok/s, not measured.
- **DeepSeek-V4-Flash (UD-IQ3_XXS, 95.9 GiB)**, the next model to pool: ~280B total but ~8-10B
  active per token (6 routed + 1 shared expert × 43 layers from its config, attention not
  counted), so an estimated ~2× the 235B's generation speed over the same split. llama.cpp
  `b94959a64` has the architecture (`LLM_ARCH_DEEPSEEK4`) and its special ops
  (`DSV4_HC_PRE/POST/COMB`, `LIGHTNING_INDEXER`) on HIP, Vulkan, SYCL and CPU, so the B580 and
  the server CPU can both take layers. Expert tensors use the usual `ffn_{gate,up,down}_exps`
  names. Layers are ~2.2 GiB each (43 of them), so splits are coarse. The download was
  stopped at 40 of 96 GiB and deleted; it starts from scratch next time
  (`unsloth/DeepSeek-V4-Flash-GGUF`, folder `UD-IQ3_XXS`, 4 shards).
