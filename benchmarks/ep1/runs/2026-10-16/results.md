# Ep 1 measurements, 2026-10-16

Same software for every row. Logs for each cell are in `logs/`.

## gpt-oss-20b, 32K (control)

| Tier | `--device` | tok/s | used card free (MiB) |
|---|---|---|---|
| 16GB | ROCm0 | 134.98 | 3,502 (9070 XT) |
| 32GB | ROCm1 | 142.37 | 20,380 (R9700) |
| 48GB | ROCm0,ROCm1 | 128.40 | 10,918 (9070 XT, tightest) |

## Qwen3.6-35B-A3B UD-Q6_K

Smallest `--n-cpu-moe` on the 9070 XT alone (1024 MiB margin): 32K **22**, 128K **24** (of 40 expert layers). No offload at all: 32K fails, 128K fails.

| Config | 32K tok/s | 128K tok/s | 128K free: 9070 XT / R9700 (MiB) |
|---|---|---|---|
| 9070 XT alone, offload | 44.58 | 43.36 | 1,055 / 32,567 |
| Both cards, same offload (the twist) | 44.09 | 42.87 | 13,817 / 18,820 |
| R9700 alone, no offload | 78.44 | 78.44 | 15,942 / 2,725 |
| Both cards, no offload (as written) | 71.72 | 71.75 | 4,293 / 11,718 |

Where the experts live, 9070 XT alone:

| Context | Expert layers on GPU | Expert layers on CPU (`--n-cpu-moe`) |
|---|---|---|
| 32K | 18 | 22 |
| 128K | 16 | 24 |

## Qwen3.8-27B UD-Q6_K, 128K

| Config | MTP | tok/s | Draft acceptance |
|---|---|---|---|
| Both cards | on | 56.30 | 84.2% |
| R9700 alone | on | 55.78 | 84.2% |
| R9700 alone | off | 55.79 | n/a |
| 9070 XT alone | on | **did not fit** | n/a |

## Real 128K depth

| Preset | Prefill tok/s | Generation at depth tok/s | Draft |
|---|---|---|---|
| qwen3.6-35B-A3B-q6-128k | 3,194.2 | 36.91 |  |
| qwen3.8-27B-q6-128k | 761.4 | 21.93 | 50.7% |

Empty-context generation for the 'kept' column: Qwen3.6 128K and Qwen3.8 both-cards rows above.

## Correction (added after the run)

`q38-rocm1-nomtp` above is **invalid**: appending `--spec-type none` did not turn MTP off (same 55.79 tok/s and
84.2% acceptance as with MTP). Rerun with the preset's `spec-type` line removed: **24.06 tok/s**, R9700 7,375 MiB free
(`q38-rocm1-nomtp-fixed.txt`). See FINDINGS.md.
