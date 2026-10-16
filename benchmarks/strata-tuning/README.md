# Strata tuning sweep

Strata 0.1.43's opt-in settings against setup's defaults, measured 2026-10-12
on the production config: Qwen3.8-Flash-Next IQ3_XXS, R9700 + 9070 XT layer
split, 200K context, int8 KV, resident low-RAM mode, 30 GB of RAM.

**Verdict: `--pipeline-windows 2` plus `STRATA_STAGE_TRIM=1` (with
`"layer_split": "33"`), +17.5% generation for -3% prompt reading. Now the
production config.**

## Method

`sweep.py`. A fresh server per arm, so nothing is cached between arms. Prefill:
one cold 29,408-token prompt (this repo's own docs), the size of Claude Code's
first turn. Decode: 6 fresh prompts (3 code, 3 prose) at temperature 0,
thinking off, 1,000 tokens max; tok/s is all generated tokens over all
generation time. The baseline ran first and last: 80.7 / 80.5 tok/s and
1,700 / 1,703 tok/s, so drift is under 0.3%.

## Results

| arm | prefill tok/s | decode tok/s | code (3) | prose (3) |
|---|---|---|---|---|
| defaults | 1,700 | 80.7 | 102 / 103 / 102 | 68 / 67 / 68 |
| `--adapt-async 1` | 1,690 | 80.5 | 103 / 105 / 99 | 69 / 65 / 67 |
| `--pipeline-windows 2` | 1,451 (-15%) | **90.9 (+13%)** | 123 / 135 / 126 | 71 / 67 / 70 |
| `STRATA_SPLIT_OWN=1` | 1,543 (-9%) | 79.4 | 95 / 100 / 98 | 65 / 67 / 67 |
| `STRATA_STAGE_TRIM=1`, split 33 | **1,804 (+6%)** | 84.2 (+4%) | 105 / 105 / 103 | 73 / 70 / 70 |
| `--spec 3` | 1,675 | 77.6 | 93 / 94 / 89 | 68 / 67 / 68 |
| `--spec 5` | 1,671 | 81.3 | 103 / 111 / 103 | 63 / 66 / 67 |
| `--spec 6` | 1,727 | 80.5 | 103 / 112 / 105 | 63 / 64 / 67 |
| **pipeline-windows 2 + stage trim** | 1,653 (-3%) | **94.8 (+17.5%)** | 130 / 143 / 125 | 76 / 73 / 78 |
| the same + `--spec 5` | 1,866 | 89.7 | 121 / 127 / 121 | 72 / 72 / 72 |

* **`--pipeline-windows 2` is the opposite of the 2x RTX 3090 result** in
  Strata's MULTI_GPU.md (flat decode, +17-28% prefill there; -3% decode on 2x
  R9700). On R9700 + 9070 XT it is a decode win, mostly on code, whose drafts
  are accepted more, so more of the next window's guess holds.
* **Stage trim** loads each card's own layers' dense weights only; the freed
  VRAM goes to the expert cache. It needs explicit split points (`33` is what
  `auto` picks here) and pays back most of the pipeline's prefill cost.
* `--adapt-async` does nothing here: the cards already hold 99.7% of the
  routed experts, so there are few swaps to hide. `STRATA_SPLIT_OWN` helped
  2K and 16K prompts in Strata's own figures on this card pair; at 29K it
  costs 9%.
* `--spec 4` (setup's) stays: 3 is worse, 5 and 6 trade code for prose.
* After switching, a code answer ran 131.7 tok/s and the output was correct;
  prose stayed clean.

## Production config

In `~/code/Strata/strata-iq3_xxs.json`: `"--pipeline-windows", "2"` in
`args`, `"STRATA_STAGE_TRIM": "1"` in `env`, `"layer_split": "33"`. The file
before is `strata-iq3_xxs.json.pre-tuning`.

**`setup.sh --setup` undoes two of the three:** it rewrites `layer_split` and
does not carry hand-added `args` (it keeps the `env` entry). Re-apply after
any setup run.

## One card or two: R9700 alone against both cards (2026-10-16)

`one_vs_two.py`, the same prompts and method as above, 200K context. The R9700
alone runs without the two split-only settings (pipeline windows, stage trim).
Order: both, R9700, both again; the third run was interrupted once and redone.

| | Prompt reading (29K) | Generation | Code (3) | Prose (3) | Expert cache |
|---|---|---|---|---|---|
| Both cards, tuned | 1,756 tok/s | 93.9 | 131 / 137 / 127 | 76 / 73 / 74 | 14,227 + 6,065 slots |
| R9700 alone | 1,566 tok/s | **86.2** | 98 / 108 / 108 | 70 / 73 / 79 | 16,896 slots, 25.7 GiB |
| Both cards, again | 1,774 tok/s | 96.9 | 133 / 146 / 127 | 75 / 75 / 76 | |

* **Both cards win here**, the one model on this box where they do: +11% on
  generation (95.4 average against 86.2), +13% on prompt reading, **+31% on
  code** (136 against 105 average), prose about level.
* The R9700 alone still served 95-99.6% of expert lookups from VRAM: Strata's
  adaptive cache follows the conversation, so the single card loses less than
  its 69% of cached expert pairs suggests.
* The repeat moved +3% (93.9 -> 96.9), more than this box's usual 0.3%, but
  well inside the gap.
