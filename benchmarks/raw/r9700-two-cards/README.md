# Two-card measurements, 2026-10-05

Raw material behind [`r9700+rx9070.md`](../../../r9700+rx9070.md).

**The original logs are gone.** Everything ran from a session scratchpad under
`/tmp`, which is a RAM disk on this box, and the machine rebooted that night.
What is here instead:

* **The scripts**, recreated from the session that ran them. Configs, flags and
  prompts are unchanged. Two differences, both cosmetic: `dense.sh` merges what
  ran as two scripts (`dense.sh`, `dense2.sh`) behind a `qwen38|rest` argument,
  and log paths moved from the session directory to `/tmp`. One addition:
  `moe_sweep.py` takes a `PRESETS` path, so the single-card presets can be
  swept without touching the live file the router reads.
* **`results.txt`**, transcribed from that session's tool output. It is a
  transcription, not a capture: the summary lines exactly as printed, with long
  flag lists dropped. Every figure in it also appears in `models-preset.ini`
  comments or in commit `c18f1bc`.
* **`logs/`**, a captured rerun of the Qwen3.8 half, the same night
  (23:11-23:26): `dense.sh qwen38` and `depth.sh` through `logs/run-qwen38.sh`,
  with `qwen38-rerun.txt` as the summary and every llama-server log beside it.
  It reproduces `results.txt` sections 4-6. The Qwen3.8 32K MTP runs moved from
  `dense.sh rest` into `dense.sh qwen38` for it, and both scripts now take
  `LOGDIR` (default `/tmp`) so a rerun can keep its logs.
* **`logs/gemma-sweep.txt`**, the eight Gemma 4 rows of the MoE sweep, rerun
  23:30-23:39 through `logs/run-gemma.sh` against `logs/presets-4c4b695.ini`
  (the single-card presets, so "as written" is the same before). It reproduces
  the Gemma rows of `results.txt` section 1. `moe_sweep.py` also takes `LOGDIR`
  now.
* **`logs/rest-run.out`** (`run-rest.sh`, 2026-10-06 07:37-08:13): everything
  else. The Qwen3.6, Laguna and GLM rows of the MoE sweep
  (`moe-rest-sweep.txt`), `dense.sh rest` (Qwen3.5-27B, Muse), and
  `preset_probe.py` on the presets the first session never measured on two
  cards (`presets-unmeasured.txt`). Then gpt-oss-20b and Qwen3.5-9B pinned to
  the R9700 alone (`presets-one-card.txt`). With this, `results.txt` is fully
  superseded by captured output.
  The one-card runs reused the server-log names, so
  `sweep-gpt-oss-20b-A3.6B-32k-0.log` and `sweep-qwen3.5-9B-uncensored-32k-0.log`
  hold the R9700-only run; the two-card figures for them are in
  `presets-unmeasured.txt`.
* **`logs/depth-presets.txt`** (`depth_presets.sh`, 2026-10-07 10:59-11:25,
  b11434): every MoE 128K preset plus Qwen3.8 IQ4_XS and Q6_K at real 128K
  depth, each preset exactly as written in `models-preset.ini`, with its
  server log as `logs/depthp-<preset>.log`. The first attempt that morning is
  `depth-presets-INVALID.txt` and `depthp-*-INVALID.log`: the script killed
  its wrapper subshell instead of llama-server, so only its first row is real.
* **`logs/q6-vs-q8.txt`** (`logs/run-q6.sh`, 2026-10-07 11:25-11:35, b11434):
  Qwen3.8 IQ4_XS, UD-Q6_K and Q8_0 at 128K and Q6_K at 256K, fit + 700-token
  probe, server logs `logs/dense-q6cmp-*.log`. A rerun of the 2026-10-06
  comparison, whose logs went with the scratchpad in a reboot.
* **`logs/glm-q8.txt`** (`logs/run-glm-q8.sh`, 2026-10-07 12:32-13:12, b11434):
  GLM-4.7-Flash Q8_0 vs Q4 fit + probe, then `depth_sweep.sh` at 8K-128K with
  three attention/KV configs and a Qwen3.6 control. The `-fa off` config at
  ctx 131072 failed to allocate (11 GB score buffer); **`logs/glm-q8-fa-pair.txt`**
  reran `-fa on`/`-fa off` at ctx 65536, `-ub 512`. Its 64K `-fa off` point was
  stopped by hand, noted in the file. Server logs `sweep-glm-*.log`, `glmq8-*.log`.
* **`logs/qwen36-quants.txt`** (`logs/run-qwen36-quants.sh`, 2026-10-07
  13:55-14:24, b11434): Qwen3.6 UD-Q4_K_M vs UD-Q6_K vs Q8_0, fit + probe at
  32K/128K/256K, 128K depth, and KLD with Q8_0 as reference (scores in
  `benchmarks/q8ref/qwen3.6-35B-A3B-*`). The first KLD base pass stalled on
  mmap and was rerun with `-lm dio`, noted in the file.
* **`logs/gemma-q8.txt`** (`run-gemma-q8.sh`): Gemma 4 Q8_0 vision fits at
  32K/128K/256K, the probe image end to end at 128K, and a Q4-vs-Q8_0 KLD run
  that came out invalid (`gemma-kld-q4-vs-q8-INVALID.txt`; see "Open" in
  r9700+rx9070.md). `gemma-ppl-diagnostics.txt` has the 8-chunk perplexity
  runs that ruled out the split, batch size and SWA cache.

| File | What it ran |
|---|---|
| `moe_sweep.py` | every MoE preset: least `n-cpu-moe` with 1 GiB free on the tightest card, then old vs new on the 700-token probe |
| `dense.sh` | `qwen38`: Qwen3.8 IQ4_XS vs Q8_0 with and without MTP, 32K-256K. `rest`: Qwen3.5-27B 64k; Muse-Glimmer 64k/128k |
| `depth.sh` | Qwen3.8 at a real 128,025-token prompt: `-ub 512` vs 1024, and the old preset |
| `results.txt` | what they printed, transcribed |
| `preset_probe.py` | any preset as written (plus `EXTRA` flags): fit, then the probe |
| `logs/` | every figure above, rerun and captured |

All three need `benchmarks/gpu-mem.sh` and `fit.sh` as of commit `4c4b695`.
Nothing else may hold a GPU while they run; `fit.sh` refuses if another
`llama-server` is up.
