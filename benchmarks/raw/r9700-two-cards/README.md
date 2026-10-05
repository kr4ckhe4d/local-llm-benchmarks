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

| File | What it ran |
|---|---|
| `moe_sweep.py` | every MoE preset: least `n-cpu-moe` with 1 GiB free on the tightest card, then old vs new on the 700-token probe |
| `dense.sh` | Qwen3.8 IQ4_XS vs Q8_0 with and without MTP; Qwen3.5-27B 64k; Muse-Glimmer 64k/128k |
| `depth.sh` | Qwen3.8 at a real 128,025-token prompt: `-ub 512` vs 1024, and the old preset |
| `results.txt` | what they printed |

All three need `benchmarks/gpu-mem.sh` and `fit.sh` as of commit `4c4b695`.
Nothing else may hold a GPU while they run; `fit.sh` refuses if another
`llama-server` is up.
