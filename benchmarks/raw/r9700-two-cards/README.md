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
