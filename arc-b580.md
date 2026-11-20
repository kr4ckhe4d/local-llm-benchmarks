# Arc B580 — Vulkan against SYCL

Measured 2026-11-20 on a second machine, `ubuntulocal`, built from the
previous desktop's parts. Nothing here is the RDNA4 box: different GPU, vendor,
driver stack and host. Read these numbers next to each other, not next to the
RX 9070 XT / R9700 tables.

**The result in one line:** on the B580, llama.cpp's SYCL backend generates
**1.9-3.5× faster** than its Vulkan backend on every model and quant tried,
dense and MoE (2.5× or more on everything except dense Q4_0). Vulkan still reads prompts faster on dense models that sit entirely in
VRAM. Run SYCL for anything where you wait on output.

## The machine

| | |
|---|---|
| GPU | Intel Arc B580 (Battlemage G21), 12 GB GDDR6, 456 GB/s rated, ASRock, Gen4 x8 |
| CPU | Ryzen 9 5950X, 16C/32T |
| RAM | 60 GiB usable, DDR4-3200 |
| OS | Ubuntu 26.04.1, kernel 7.0.0-43, in-tree `xe` driver |
| Vulkan | Mesa 26.0.8 (ANV), `KHR_coopmat`, integer dot, ReBAR on |
| SYCL | oneAPI 2026.2 (`icpx`, oneMKL SYCL, oneDNN), compute-runtime 26.05.37020, Level Zero |
| llama.cpp | `b94959a64` (2026-11-19), same commit for both builds |

Full versions, build lines and device strings:
[environment.txt](benchmarks/raw/arc-b580/environment.txt).

The two builds report different memory: Vulkan sees 12,216 MiB, SYCL 11,605
MiB. That ~600 MiB matters at the edge: gpt-oss-20b fits whole on Vulkan and
does not on SYCL (below).

## Method

[`arc-b580-bench.sh`](benchmarks/arc-b580-bench.sh) runs `llama-bench` with
identical arguments on both builds: `-ngl 99 -fa 1`, pp512 and tg128, at an
empty context and 16,384 tokens deep, 3 repetitions, JSON output. SYCL is
pinned to Level Zero (`ONEAPI_DEVICE_SELECTOR=level_zero:0`). MoE runs add the
same `-ncmoe` to both builds. Raw JSON and stderr for every run:
[benchmarks/raw/arc-b580/](benchmarks/raw/arc-b580/).

The dense model is Qwen3.5-9B-Uncensored, the same Q8_0 GGUF as
`benchmarks/qwen3.5-9B-Uncensored-Q8_0`. Q4_K_M and Q4_0 were requantized from
that Q8_0 on the server (`llama-quantize --allow-requantize`), so they carry
Q8_0's rounding on top of their own. Fine for speed, not for quality claims.

## Results

### Dense: Qwen3.5-9B

| Quant | Size | pp512 Vulkan | pp512 SYCL | tg128 Vulkan | tg128 SYCL | SYCL / Vulkan, tg |
|---|---|---:|---:|---:|---:|---:|
| Q8_0 | 8.86 GiB | **1,720** | 808 | 12.6 | **44.0** | 3.5× |
| Q4_K_M | 5.23 GiB | **1,680** | 819 | 22.4 | **63.5** | 2.8× |
| Q4_0 | 4.94 GiB | **1,771** | 621 | 32.7 | **63.6** | 1.9× |

16K tokens deep:

| Quant | pp512 Vulkan | pp512 SYCL | tg128 Vulkan | tg128 SYCL |
|---|---:|---:|---:|---:|
| Q8_0 | **909** | 750 | 12.1 | **39.7** |
| Q4_K_M | **904** | 758 | 20.9 | **55.1** |
| Q4_0 | **929** | 760 | 29.6 | **55.0** |

Vulkan's prompt lead halves with depth (2.1× empty, 1.2× at 16K); SYCL's
prefill barely moves.

### MoE: gpt-oss-20b (MXFP4, 11.27 GiB, 3.6B active)

All on the GPU, Vulkan only (SYCL fails to allocate its 433 MiB compute buffer
at 16K: [log](benchmarks/raw/arc-b580/sycl-gpt-oss-20b-MXFP4.log)):

| | pp512 | tg128 | pp512 @ 16K | tg128 @ 16K |
|---|---:|---:|---:|---:|
| Vulkan, all on GPU | 2,280 | 29.7 | 1,362 | 27.5 |

With two layers of experts in RAM (`-ncmoe 2`) so both builds fit:

| | pp512 | tg128 | pp512 @ 16K | tg128 @ 16K |
|---|---:|---:|---:|---:|
| Vulkan | **1,320** | 28.0 | **949** | 26.0 |
| SYCL | 889 | **91.6** | 566 | **83.0** |

**The best gpt-oss-20b config on this card is SYCL with two expert layers on
the CPU: 91.6 tok/s, 3.1× Vulkan with everything resident.** Moving experts
off the GPU costs Vulkan 42% of its prefill and 6% of its generation.

### MoE larger than VRAM: Qwen3.6-35B-A3B (UD-Q4_K_M, 20.6 GiB, 3B active)

`-ncmoe 22` (22 of 40 layers' experts in RAM) is the lowest that fits SYCL at
16K; 20 fails to create the context, 18 and below fail to load. Same value on
both builds:

| | pp512 | tg128 | pp512 @ 16K | tg128 @ 16K |
|---|---:|---:|---:|---:|
| Vulkan | 238 | 19.1 ± 1.4 | 194 | 19.5 |
| SYCL | **464** | **48.1** | **394** | **44.7** |

A 35B MoE at 48 tok/s on a 12 GB card, with more than half its experts on a
DDR4 CPU. Here SYCL also wins prefill, by 2×: with experts in RAM the prompt
path is no longer the dense GPU matmul Vulkan is good at.

## Why Vulkan generates slowly here

Not the card. With the same weights, SYCL reads them at roughly 370 GB/s
(Q8_0: 44.0 tok/s × 7.86 GiB per token, the 8.86 GiB file minus its 1.0 GiB
token-embedding table, which is indexed rather than read), 81% of the rated
456 GB/s. PCIe trains at Gen4 x8 (the card's width; the x1 at 2.5 GT/s that
`lspci` shows on 08:00.0 is the card's internal bridge), and the GPU clock sits
at 2,850 MHz under load.

Vulkan's per-op profile of one Q8_0 decode step
([vulkan-q8_0-decode-profile.txt](benchmarks/raw/arc-b580/vulkan-q8_0-decode-profile.txt))
puts 75 of its 78.6 ms in `MUL_MAT_VEC q8_0` — the quantized matrix-vector
kernels that are pure weight streaming — at 155-227 GFLOP/s, about **115 GB/s
of weight reads, a quarter of the rated bandwidth**. Everything else in the
step (norms, RoPE, the gated-delta-net layers, attention) adds up to ~3.6 ms.
So it is the matvec shaders on Mesa's ANV driver for Xe2, not overhead.

No `GGML_VK_*` switch helps:

| Q8_0 tg128 | tok/s |
|---|---:|
| default | 12.57 |
| `GGML_VK_DISABLE_COOPMAT=1` | 12.57 |
| `GGML_VK_DISABLE_F16=1` | 12.57 |
| `-fa 0` | 12.58 |
| `GGML_VK_DISABLE_INTEGER_DOT_PRODUCT=1` | 9.59 |

The per-quant spread fits a shader-quality explanation: Q4_0, the simplest
block format, reaches roughly 160-175 GB/s on Vulkan; Q4_K_M and Q8_0 roughly
105-125 GB/s (ranges because the requants' embedding-table type is not
separated out).

## What to run on this card

- **SYCL build for chat, agents, anything output-bound.** Q4_K_M generates as
  fast as Q4_0 on SYCL and prefills 32% faster, at better quality.
- **Vulkan only for long prompts with short answers on a dense model that fits
  whole**, and even there the lead is 1.2× at 16K.
- **MoE with expert offload is the good use of 12 GB + 60 GB RAM.**
  Qwen3.6-35B-A3B at 48 tok/s beats the dense 9B Q8_0 (44) while being a much
  larger model.
- Every new shell needs `source /opt/intel/oneapi/setvars.sh` and
  `ONEAPI_DEVICE_SELECTOR=level_zero:0`.

## Caveats

- One machine, one driver snapshot. Mesa's Xe2 matvec path is under active
  work; re-run `arc-b580-bench.sh` after a Mesa or llama.cpp update before
  repeating "Vulkan is slow" as fact.
- The boot log has 15 × `xe ... PCODE Mailbox failed: -6 Illegal Command`.
  Given SYCL reaches 81% of rated bandwidth, it is not costing memory speed;
  probably unsupported power/fan queries, possibly fixed by a BIOS or card
  firmware update.
- Throughput only. No KLD, code-quality or tool-calling runs on this box, and
  the Q4 quants are requants of a Q8_0.
- The first SYCL Q4_K_M run in exploration had one slow repetition (39.3 ±
  34.5); every rerun, including the recorded one, is 63.5-63.6 ± 0.3.
