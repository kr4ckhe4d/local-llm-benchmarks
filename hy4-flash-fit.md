# Hy4-flash on 30 GB of RAM — why it does not fit, and what would change that

Checked 2026-11-27 against the machine in [README.md](README.md) (RX 9070 XT +
Radeon AI PRO R9700, 9800X3D, 30 GB DDR5-6000, ROCm 7.2.4).

**Nothing in this file was measured here.** No weights were downloaded and no
engine was run. Every size, speed and quality figure below is quoted from
Tencent's and Strata's own model cards, with the source named each time. It is
a fit analysis, not a benchmark — the rest of this repo is the other way round.

**Verdict up front: Hy4-flash does not fit on this box, and VRAM is not the
reason.** 47.8 GiB of VRAM is more than any published configuration asks for.
The blocker is **30 GiB of system RAM**, against a documented floor of 64 GiB,
and a 62.94 GiB lookup table that is paged from disk through a cache this box
does not have room for. A RAM upgrade, not a GPU, is what moves this.

---

## The model

[`tencent/Hy4-flash`](https://huggingface.co/tencent/Hy4-flash) — **220B total
parameters, 12B active per token**, 42 layers, text and images in, 1,048,576
context. `model_type` is `hy_v4_flash`; the GGUF builds declare the
architecture string `hy_v4_next_dfly`.

**64B of the 220B sit in an Engram lookup table**, not in the trunk. `config.json`
puts Engram heads on layers 2, 12, 22 and 32, eight heads each over vocabularies
of ~10.31M entries, max n-gram size 3. That table is what the engines read on
demand from disk rather than hold resident, and it is why the vendors can claim
an 8 GiB graphics card is enough. It is also, on this box, the problem.

The attention is DSA-style: `compressed_indexer_candidate_topk: 2048`,
`compressed_indexer_group_topk: 512`, compression ratio 4. That indexer is what
the DFly2 drafter reads, below.

## What the two engines ask for

**llama.cpp GGUF** — [`AngelSlim/Hy4-flash-GGUF`](https://huggingface.co/AngelSlim/Hy4-flash-GGUF),
sizes from its own table:

| File | Model size | bpw overall | bpw excl. Engram |
|---|---:|---:|---:|
| `Hy4-flash-Q4_K_M` | 156.79 GiB | 6.05 | 5.27 |
| `Hy4-flash-SPARK-4Bit` | 151.3 GiB | 5.84 | 4.78 |
| `Hy4-flash-SPARK-4Bit-Fast` | 148.6 GiB | 5.74 | 4.63 |
| `Hy4-flash-Q3_K` | 144.70 GiB | 5.58 | 4.62 |
| `Hy4-flash-IQ2-AH` | 125.73 GiB | 4.85 | 3.60 |

**Strata packs** — [`strata-engine/Hy4-Flash-Strata`](https://huggingface.co/strata-engine/Hy4-Flash-Strata),
sizes and requirements from its own table. "Memory in use" is RAM plus VRAM
together; "on disk" includes the shared `Hy4-Flash-Engram-Q8.strata` (62.94 GiB)
that every pack needs:

| Pack | RAM asked | Graphics card | Memory in use | On disk |
|---|---:|---|---:|---:|
| `SQ-64` | 64 GiB | 8, 12 or 16 GiB | 59.4 GiB | 129.61 GB |
| `SQ-96` | 96 GiB | 8 or 12 GiB | 85.1 GiB | 157.16 GB |
| `SQ-128` | 128 GiB | 8 or 12 GiB | 107.5 GiB | 181.23 GB |

## Against this box

| | Here | Smallest published config (`SQ-64`) |
|---|---:|---:|
| System RAM | **30 GiB** (27 available) | 64 GiB |
| VRAM | 47.8 GiB (15.92 + 31.86) | 8–16 GiB |
| Free disk on `/mnt/fast` | 269 GB | 129.61 GB |

The sum is not the obstacle — 30 + 47.8 = 77.8 GiB covers SQ-64's 59.4 GiB of
resident weights, and AngelSlim's Strata guide has `--resident-experts` to split
experts between VRAM and RAM. **The shape is wrong.** These packs are built for
the opposite machine: a large pool of host RAM feeding a small card. This box is
a small pool of host RAM feeding 47.8 GiB of cards, and no amount of VRAM
substitutes for the part that has to be RAM.

**The Engram table is the hard stop.** AngelSlim's own guide: *"The Engram table
in the second shard is read on demand. Accessed pages can remain in the OS page
cache."* With 30 GiB of RAM mostly holding trunk experts, there is no page cache
left for a 62.94 GiB table, so every token turns into random NVMe reads. That is
the same memory-pressure cliff that froze this box twice during the RPC work —
see the `MemAvailable` watchdog and the Vulkan GTT spill in
[rpc-qwen3-235b.md](rpc-qwen3-235b.md).

The llama.cpp route is worse, not better: the smallest GGUF, `IQ2-AH` at
125.73 GiB, exceeds RAM and VRAM combined, so `-ngl 99` is not on the table at
any quant.

## Engine support: llama.cpp has it, Strata's is still a PR

**llama.cpp: support landed upstream on 2026-11-25**, two days before this entry,
and not by the route AngelSlim's card points at. Their own
[PR #32517](https://github.com/ggml-org/llama.cpp/pull/32517) is still unmerged;
what went in is `c94333133`, *"model : add hy_v4_flash on the DSA iSWA cache"*
([PR #32960](https://github.com/ggml-org/llama.cpp/pull/32960), by Pascal), which
runs the model on `llama_kv_cache_dsa_iswa` with the pools rebuilt per ubatch by
`set_input_kpool()` and the selection through `ggml_top_k_mask`. It carries real
Engram tensors — `LLM_TENSOR_ENGRAM_KV_B`, `ENGRAM_LOOKUP_NORM`, `ENGRAM_PRE_GAMMA`,
`ENGRAM_HC_SCALE` — so the lookup table is a first-class part of the graph.

**One thing to check before trusting that:** upstream registers the arch strings
`hy_v4` and `hy_v4_flash`, while the AngelSlim GGUFs declare **`hy_v4_next_dfly`**.
Those are not the same string, so whether AngelSlim's files load on upstream as
published, or need reconverting from `tencent/Hy4-flash`, is unresolved here and
cannot be resolved without downloading one.

**The router carries it as of 2026-11-27.** `inkling2-strata-ideas` was rebased
onto upstream `15fcfc735` that day — 169 commits, 29 replayed by hand because
upstream had moved its fusion dispatch into a new `fusion.cu` — and `~/llama.cpp`
now builds from that tip, so `hy_v4_flash` is in the router binary. What is still
unknown is whether the arch runs on `gfx1201`: nothing here has loaded it, and
ROCm is untried for the DSA iSWA cache path.

**Strata:** support is [PR #7120](https://github.com/Niko1221/Strata/pull/7120).
AngelSlim's GGUF guide builds it `-DSTRATA_ENABLE_CUDA=ON` and their published
numbers are CUDA and Metal only. Strata's own speed chart, however, lists
**"R9700 or RX 9070 XT: 62 tok/s, prompt 1,122"** — this exact GPU pair, already
measured by someone else, on a machine that evidently had the RAM.

## The drafters

The DFly line that this repo already tracks through
[dflash2-qat-q2.md](dflash2-qat-q2.md) and [dspine-qwen3.8-27b.md](dspine-qwen3.8-27b.md)
continues here:

- **DFly, in GGUF already**: `hy4-flash_dfly_Q8_0.gguf`, 0.84 GiB, in the
  AngelSlim repo. Their 16 GiB-VRAM Strata table has it worth **+5% on prose
  (36.8 → 38.7 tok/s) and +27% on code (37.5 → 47.6)**. The code-heavy skew
  matches what DFlash2 and DSpine did on Qwen3.8-27B.
- **DFly2**: [`AngelSlim/Hy4-flash-DFly2-B6`](https://huggingface.co/AngelSlim/Hy4-flash-DFly2-B6),
  5.81 GiB safetensors, **no GGUF**. `block_size: 6`, 3 layers, and a drafter
  that is itself a 128-expert MoE (3 active, 1 shared). It reads the target at
  layers 32/36/40, the target's KV at 33/37/41, and that layer's index picks at
  `target_index_topk: 2048`. Paper: [arXiv:2611.34776](https://arxiv.org/abs/2611.34776),
  *"Turbocharging Long-Context Speculative Decoding by Sharing the Target's Sparsity"*,
  25 Nov 2026. Trained with [AngelSpec](https://github.com/Tencent/AngelSpec)
  ([arXiv:2607.25852](https://arxiv.org/abs/2607.25852)).

**DFly2 is not a drafter you can point at the models in this repo.** It works by
reading the target's own MLA latents and DSA top-k picks; a target with neither —
Qwen3.8-27B, Gemma 4, Inkling-2-Mini, Nemotron 3.5 Lightning — has nothing to
share, so it is no substitute for an in-file MTP head or a DFlash2 drafter.

Worth noting for later: the router branch already carries `--spec-type`
`draft-dflash2`, `draft-dspark` and `draft-eagle3`, plus the DSA KV cache
(`llama-kv-cache-dsa.cpp`, `LLM_ARCH_GLM_DSA`, `LLM_ARCH_DEEPSEEK41`). If a
`draft-dfly2` lands upstream, this box could compare DFly2 against DSpark on the
same hardware — the central claim of the announcement — on whatever DSA target
does fit.

## Quality, as published

Strata's pack card gives mean KL divergence against BF16 over eight held-out
512-token prompts:

| Pack | Reasoning | Tool-calling |
|---|---:|---:|
| `SQ-128` | 0.08789 | 0.17969 |
| `SQ-96` | 0.13591 | 0.23661 |
| `SQ-64` | 0.23206 | 0.51828 |

**Read these beside this repo's own KLD numbers with care — the methodology is
not the same** (different base model, 512-token prompts, 4,096 scored positions,
their harness not `kld-test.sh`). Taken at face value the direction is still
stark: the only pack that would even be in reach here, `SQ-64`, sits at 0.232
and 0.518, where this repo's shipping quants live at 0.0020 (Qwen3.8-27B
UD-Q6_K) and treats 0.0179 (IQ4_XS) as the point where quality starts to cost.
The cheap pack is a different kind of object from the quants in
[gemma-4-12b-quants.md](gemma-4-12b-quants.md).

## What would change the answer

1. **64 GiB of DDR5-6000.** This is the whole fix. It puts `SQ-64` at its
   documented configuration, with 47.8 GiB of VRAM where the card only needs 8–16,
   and leaves real page cache for the Engram table.
   [ddr5-9800x3d.md](ddr5-9800x3d.md) already measures what host memory does to
   CPU-offloaded MoE here, so the before/after framing exists.
2. **RPC across both boxes.** `ubuntulocal` has 60 GB DDR4, and
   [rpc-qwen3-235b.md](rpc-qwen3-235b.md) already ran a 97 GiB model over the
   2.5 GbE link at 5.5 tok/s with 35 of 94 layers in that DDR4. Hy4-flash is
   larger on disk but **12B active against Qwen3-235B's 22B**, so the per-token
   transfer is smaller. Now that `hy_v4_flash` is upstream this needs the same
   build on both ends — the RPC protocol is versioned, so `ubuntulocal` has to
   match commit for commit. Strata has no RPC backend.
3. ~~**The router branch rebased onto upstream, built for ROCm.**~~ **Done on
   2026-11-27**: the router builds from `484c0fa9a`, upstream `15fcfc735` plus
   this repo's 29 Inkling-2 commits and two fixes to the rebase, so
   `hy_v4_flash` is present. It was never
   sufficient on its own — memory is still the blocker — and whether the arch
   runs on `gfx1201` is untested.

Until one of those, the actionable part of this release for this repo is not
Hy4-flash at all — it is watching for `draft-dfly2` upstream.

## Sources

- [`tencent/Hy4-flash`](https://huggingface.co/tencent/Hy4-flash) `config.json` — parameter layout, Engram heads, DSA indexer settings
- [`AngelSlim/Hy4-flash-GGUF`](https://huggingface.co/AngelSlim/Hy4-flash-GGUF) `README.md`, `README_strata.md` — GGUF sizes, the 16 GiB-VRAM DFly table, build and launch instructions
- [`strata-engine/Hy4-Flash-Strata`](https://huggingface.co/strata-engine/Hy4-Flash-Strata) `README.md` — pack sizes, RAM floors, KLD, the cross-machine speed chart
- [`AngelSlim/Hy4-flash-DFly2-B6`](https://huggingface.co/AngelSlim/Hy4-flash-DFly2-B6) `config.json` — drafter shape
- [arXiv:2611.34776](https://arxiv.org/abs/2611.34776) (DFly2), [arXiv:2602.21233](https://arxiv.org/abs/2602.21233) (AngelSlim), [arXiv:2607.25852](https://arxiv.org/abs/2607.25852) (AngelSpec)
- Local: `free -g`, `df -h /mnt/fast`, `rocm-smi --showmeminfo vram`, `git log` in `~/llama.cpp`
- llama.cpp upstream `c94333133` and its arch table (`src/llama-arch.cpp`), read at `origin/master` `15fcfc735` on 2026-11-27
