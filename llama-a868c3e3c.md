# llama.cpp `a868c3e3c` — what 882 commits bought Qwen3.8

Measured 2026-10-02, after updating llama.cpp from `b10463` (`7c35571e5`,
2026-08-17) to build 11345 (`a868c3e3c`, 2026-10-01).

**This file does not replace [README.md](README.md).** Every number there was
measured on `7c35571e5` and stays the record of that build. This is a
before/after on the two Qwen3.8 presets most used day to day, run back to
back on the same box (DDR5 / 9800X3D, see [ddr5-9800x3d.md](ddr5-9800x3d.md)).

## Result

Prefill is the headline, and it was not predicted. Reading the commit log
beforehand, the expected gain was "small, MTP only" — nothing in the range
targets `qwen35` on RDNA4. Measured:

| Preset | Metric | `7c35571e5` | `a868c3e3c` | Change |
|---|---|---|---|---|
| `qwen3.8-32k-mtp` | tg, shallow | 68.20 | 70.05 | **+2.7%** |
| | tg @ 16.8K depth | 61.35 | 64.11 | **+4.5%** |
| | prefill, 16,852 tok | 916 | 1169 | **+27.6%** |
| | draft acceptance, shallow / depth | 86.8% / 85.5% | 84.6% / 85.7% | ~flat |
| `qwen3.8-32k` (no MTP) | tg, shallow | 30.08 | 32.07 | **+6.6%** |
| | tg @ 16.8K depth | 26.84 | 28.41 | **+5.8%** |
| | prefill, 16,852 tok | 959 | 1193 | **+24.5%** |

tok/s throughout. Each cell is the mean of two server loads; the two loads of
each build agree to within 1%, and within a load the runs agree to ±0.3 tok/s.

* **Prefill +25-28% is the change you will feel.** Long agentic histories
  spend most of their wall time in prefill, so a 16K-token turn now starts
  generating ~4s sooner on `32k-mtp` (18.4s → 14.4s of prefill).
* **MTP gains less than plain decoding** (+2.7-4.5% vs +5.8-6.6%). The draft
  forward pass was already cheap, so a faster base pass moves a smaller share
  of each step.
* **The shallow acceptance drop (86.8 → 84.6%) is a different output, not a
  worse drafter.** Numerics changed, so the greedy 700-token completion is no
  longer the same text; acceptance at depth is unchanged. One prompt is too
  few to call a 2-point move in either direction.
* The old build reproduces the stored figure: 68.54 tok/s and **86.8%**
  acceptance on its first load, against 69.14 / 86.8% recorded on 2026-08-29.
  So the probe change below did not shift the baseline.

Not bisected. The likeliest contributors in range are graph capture for the
MTP draft (`2f3fd0252`) and the RMS_NORM+SCALE fusion (`1ab7e5ad2`), but
neither explains a prefill gain on its own, and no commit was isolated.

## Method

```
OLD  ~/llama.cpp-7c35571e5/build/bin/llama-server   (git worktree, own build)
NEW  ~/llama.cpp/build/bin/llama-server
```

* **ABBA order** per preset — old, new, new, old — so warm-up and thermal
  drift cancel rather than favour whichever build ran second.
* Preset flags exactly as in `models-preset.ini`, `-ngl 99 -np 1`:
  * `32k-mtp`: Q3_K_XL-v3, `-c 32768 -ub 512 -b 2048 -fa on -ctk q4_0 -ctv q4_0 --spec-type draft-mtp`
  * `32k`: IQ4_XS-v3, `-c 32768 -ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0`
* Per load: `throughput-test.py` shallow (n=3) then `--depth 16384` (n=2), one
  discarded warmup each, prompt cache off.

Raw output, per-run JSON timings and the driver are in
`benchmarks/raw/ab-7c35571e5-vs-a868c3e3c/`.

## Copying the binary is not a backup

The first attempt at a "before" binary was `cp build/bin/llama-server /tmp/`,
as the README used to advise. It does not work:

```
$ readelf -d llama-server | grep RUNPATH
 Library runpath: [/home/nipuna/llama.cpp/build/bin:/opt/rocm/lib:]
```

Since llama.cpp moved to shared libraries, the server is a thin executable
that loads `libllama`, `libggml-hip` and five others from `build/bin`. A copied
binary runs whatever was built there last — so it would have benchmarked the
*new* code twice, and after a failed build it would not start at all. The old
build here is a `git worktree` at the previous commit with its own `build/`;
`ldd` confirms all eight libraries resolve inside it.

## The throughput probe, rebuilt

The 700-token probe in `run-suite.sh` was an inline `curl` loop. Reviewing it
for this comparison turned up five defects, now fixed in
`benchmarks/throughput-test.py`:

1. **Its `pp` column measured nothing.** The prompt is ~54 tokens and runs 2-3
   hit the prompt cache — the stored `pp 50.4 tok/s` is one re-processed
   token. Requests now send `cache_prompt: false`, and real prefill comes from
   `--depth`.
2. **No warmup.** Run 1 carried first-request costs. One run is now discarded.
3. **MTP acceptance was not recorded**, though `timings` always carried
   `draft_n` / `draft_n_accepted`. The README's acceptance figures were
   copied in by hand.
4. **No mean/sd, and no check that 700 tokens were generated.** An early EOS
   would compare tok/s over different lengths; such runs are now flagged.
5. **Shallow only.** `--depth N` prefixes ~N tokens of the same filler
   `needle-test.py` uses.

The generation unit is unchanged — same prompt, temperature 0.0, thinking off,
`max_tokens: 700` — so `tg` stays comparable with every throughput number
already in the README. Even with the cache off, the shallow prefill figure is
~54 tokens of mostly fixed overhead and swings ±20 tok/s; read prefill from a
`--depth` run.

## `qwen3.8-128k` re-verified, and `-ub 1024` rejected

The 128K preset sits closest to the VRAM ceiling, so it was re-fit on the new
build (`fit.sh`, with the fixes below) and then loaded with a real
**128,212-token** prompt, 2,860 tokens short of the 131,072 limit.

| `-ub` | Needs (excl. desktop) | Peak, real 128K prompt | Free | Prefill @ 128K | tg @ 128K |
|---|---|---|---|---|---|
| 512, `7c35571e5` | 15,662 | — | 365 (desktop 277) | — | — |
| **512, `a868c3e3c`** | **15,220** | 15,784 | **520** (desktop 562) | **800 tok/s** | 9.76 |
| 1024, `a868c3e3c` | 15,443 | 16,007 | 297 | 744 tok/s | 9.79 |

GTT moved by 6 MiB or less in every row, so nothing spilled to host memory.

* **The new build needs 442 MiB less for the same flags.** The preset is
  safer now than when it shipped, even with today's desktop taking 285 MiB
  more.
* **`-ub 1024` is slower where this preset lives.** It was worth ~12% prefill
  at shallow depth on 64K, but at 128K depth it loses 7%, and it leaves 297
  MiB, 16 above the 281 danger line. n=1 per row, but slower *and* tighter
  needs no second sample. The preset stays at `-ub 512`.
* Generation at full depth is ~9.8 tok/s, a third of shallow. That is the
  q4_0 KV and full attention over 128K tokens, and the batch size does not
  move it.

## `fit.sh`: the peak was a single sample

The deep run exposed it. `fit.sh` read VRAM once, after a ten-token probe, and
called that the peak: **15,763 MiB**, against **15,784** polled during the real
128K prompt. Two causes, both fixed:

1. **One sample is not a peak.** VRAM is now polled every 0.2s from launch to
   the end of the probe. The spill check moves to the post-probe sample, which
   is the reading whose drop below `loaded` signals a migration to GTT.
2. **A ten-token prompt never runs a full batch,** so GEMM workspace that ROCm
   allocates lazily on the first large batch was never counted. The probe is
   now ~2,560 tokens (`PROBE_TOKENS`), enough to clear `-b 2048`.

Re-run, the same config reads **15,782**, within 2 MiB of the real prompt. The
cost was 21 MiB here, so earlier `fit.sh` rows read about that much
optimistic, which matters only for rows within a few tens of MiB of the
281 MiB line.

Also added: an abort if another `llama-server` is running (its VRAM was
silently counted as baseline; `ALLOW_OTHERS=1` to override), a warning when
VRAM fails to settle before `BASE` is read, and deleting the log on success.
