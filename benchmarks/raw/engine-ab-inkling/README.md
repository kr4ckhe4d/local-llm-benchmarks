# Inkling-2-Mini: llama.cpp against Strata (2026-11-23)

Same file for both engines: Unsloth's `Inkling-2-Mini-UD-Q8_K_XL.gguf` (the router's file,
`/mnt/fast/models/Inkling-2-Mini/`). Strata's own SQ-20 pack (19.3 GB `.strata`, SF4+MX8) as a fifth arm.
R9700 alone, 128K context everywhere.

* **llama.cpp** db75ce3dc = upstream + `inkling2-speedups` (the router build after this morning's update),
  the `inkling-2-mini-q8-128k` preset's flags (`--device ROCm1 -fa on -ub 128 --reasoning-budget 1024`), no drafter.
* **Strata** 0.2.20 (923e2df4d), its own `strata-inkling` engine 0.1.66 (ready-made HIP build for RDNA4),
  set up with `./setup.sh --setup --family inkling-2-mini --model UD-Q8_K_XL --gguf-dir ... --gpu 1 --context 131072
  --vision no`. With and without its DSpark drafter (`dspark-Inkling-2-Mini-Q8_0.gguf`, beside the GGUF; SQ-20
  carries its own). Configs: `strata-inkling-2-mini-*.json` here.

Client: [`../../engine-ab.py`](../../engine-ab.py), the Qwen3.6 run's method
([`../engine-ab-qwen36`](../engine-ab-qwen36/README.md)): streaming, timed on the client, output tokens counted with
`llama-tokenize` on the Q8 GGUF for every arm, the same wikitext documents (33K and 125K Inkling tokens) with a
nonce. New `--body-extra` sends Inkling's thinking switch, `chat_template_kwargs.reasoning_effort: 0`. Medians of 3
(generation, up to 1,024 tokens) and 2 (depth, 256 tokens out). Runs: `run.sh`; rows in `results.jsonl`.

## Results (tok/s)

| Arm | Code | Prose | Explain | 33K prefill | 33K decode | 125K prefill | 125K decode | Peak VRAM R9700 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| llama.cpp Q8 | 53.1 | 53.2 | 53.3 | 510 | 46.6 | 407 | **34.8** |  31.2 GB |
| Strata Q8 | 67.8 | 68.5 | 67.8 | 643 | 54.6 | 541 | 34.2 | 27.1 GB |
| Strata Q8 + DSpark | 86.4 | 62.4 | 66.9 | 641 | 33.7 | 540 | 14.7 | 30.0 GB |
| Strata SQ-20 | 69.5 | **69.7** | **69.5** | **648** | **55.7** | **544** | 34.6 | 23.3 GB |
| Strata SQ-20 + DSpark | **92.5** | 64.5 | 69.6 | 646 | 34.3 | 543 | 15.7 | 26.2 GB |
| llama.cpp Q8, branch `inkling2-strata-ideas` (7 commits, `89edf0c8a`), `-ub 512` | 59.7 | 59.7 | 59.9 | **716** | 51.5 | 532 | **37.8** | 29.6 GB |

Spread across repetitions is under 1.5% for every cell without a drafter.

The last row (added later the same day) is llama.cpp with changes taken from Strata's engine, on a branch (its first
run, at 4 commits: 57.8 / 716 / 49.7 / 530 / 36.2, rows in `results-branch-4commits.jsonl`):
[../../inkling-2-mini-UD-Q8_K_XL/strata-ideas/](../../inkling-2-mini-UD-Q8_K_XL/strata-ideas/TODO.md) and
[inkling-strata-vs-llama.md](../../../inkling-strata-vs-llama.md#tried-on-a-branch).

## Re-run, 2026-11-28: the rebased branch against Strata 0.2.22

Both engines had moved since the table above: llama.cpp's branch was rebased onto upstream `15fcfc735` and given two
fixes ([`inkling-strata-vs-llama.md`](../../../inkling-strata-vs-llama.md#rebased-onto-upstream-15fcfc735-2026-11-27)),
and Strata went from 0.2.20 to 0.2.22 (engine 0.1.66 to 0.1.69; `update-engines.sh strata`, no config key lost). Two arms,
same harness, same GGUF, same flags: `ARMS="llama-q8-branch strata-q8-nodraft" ./run.sh`. The rows are under their own
labels (`llama-q8-branch-rebased`, `strata-q8-nodraft-0.2.22`), so the rows above are untouched.

| Arm | Code | Prose | Explain | 33K prefill | 33K decode | 125K prefill | 125K decode | Peak VRAM R9700 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Strata Q8, 0.2.20 / engine 0.1.66 (above) | 67.8 | 68.5 | 67.8 | 643 | 54.6 | 541 | 34.2 | 27.1 GB |
| Strata Q8, **0.2.22 / engine 0.1.69** | 67.7 | 68.1 | 67.8 | 642 | 54.6 | 540 | 34.2 | 27.1 GB |
| llama.cpp Q8, branch, 7 commits, `89edf0c8a` (above) | 59.7 | 59.7 | 59.9 | 716 | 51.5 | 532 | 37.8 | 29.6 GB |
| llama.cpp Q8, **branch rebased, `484c0fa9a`**, `-ub 512` | 61.6 | 61.7 | 61.8 | 711 | 52.5 | 523 | 38.5 | 29.7 GB |

* **Strata did not move.** Three engine versions and 336 commits, and every cell is within 0.6% of the 0.2.20 run.
  Its update notes list an Inkling two-card expert-budget fix, a sampling default and a thinking-budget cap; none
  shows in this single-card, thinking-off run.
* **The branch gained about 3% in an empty context** (59.7 to 61.6-61.8) and 2% at 33K and 125K decode, from
  upstream's own work plus the branch's fusions kept on top of it. Plain upstream on the same GGUF decodes at
  39.5 tok/s in `llama-bench`, so this is the branch's doing, not upstream's.
* **The gap to Strata is now about 10%** in an empty context (it was 28% at the start of the branch and 14% at
  7 commits). At 33K Strata decodes 4% faster and the branch reads the prompt 11% faster (711 against 642). At 125K
  the branch decodes 13% faster (38.5 against 34.2) and Strata reads 3% faster (540 against 523).
* **One cell went the wrong way: 125K prefill is 1.7% down** (532 to 523, two repetitions each, 522.2 and 523.6
  against the old 531.5 and its pair). Not diagnosed.

Medians of 3 (generation) and 2 (depth), as above; the widest spread across repetitions is 1.3% (the branch's prose
generation, 60.97 to 61.78), inside the 1.5% bound above. The branch's `llama-server` was
built from `~/llama.cpp-inkling`, whose working tree carries the uncommitted per-request thinking patch (server
request handling only). Not re-run: the DSpark and SQ-20 arms, and the refusal probe below. Strata's
no-thinking prefill and its `temperature: 0` handling (see Pitfalls) are as they were on 0.2.20 until someone checks
them on 0.2.22.

## What it says

* **Strata is faster on the same file:** +28% decode in an empty context (68 against 53), +26% prompt reading at
  33K and +33% at 125K (a 125K prompt waits 231 s instead of 309 s), +17% decode at 33K. At 125K the decode
  speeds meet (34.2 against 34.8). Unlike Qwen3.6 (Strata 7.7x slower at 120K), it does not fall behind with depth.
* **DSpark only pays on code.** Code 68 -> 86-92, prose 68 -> 62-64, explanations even. With a long prompt it is a
  clear loss: 55 -> 34 at 33K, 34 -> 15 at 125K. These requests are sampled at temperature 1.0 (see below), which
  lowers the acceptance rate; the router preset samples at 1.0 too, so this is what real use would see.
* **SQ-20 = Q8 GGUF in speed** (within 2%). Its only gain is a smaller file and footprint, which is no gain on this
  box. Deleted after the run.

## Strata's no-thinking prefill makes Inkling refuse harmless requests

Strata's server treats Inkling as having no thinking mode. It forces `reasoning_effort: "none"` (the template
renders that as "Thinking effort level: 0", as 0 does) and, for requests without tools, ends the prompt with
`<|message_model|><|content_text|>` (`serve/inkling_dialect.py`, ~line 341), so the reply starts in visible text
with no thinking. At effort 0 Inkling normally still thinks a few hundred tokens first, and llama.cpp lets it.

Strata refused the "prose" prompt (a lighthouse keeper's radio that hears tomorrow's broadcasts) 7 times of 12
("I can't write that story as requested ...", "I can't use 'the next day' as a literal time ..."). llama.cpp
answered it 3 of 3, but greedily. [`refusal-probe.py`](refusal-probe.py) separates the two causes on llama.cpp alone,
same Q8, temperature 1.0, 10 samples each (`refusal-probe.jsonl`):

| llama.cpp, lighthouse prompt, temp 1.0 | Refused |
|---|---|
| Normal request: brief think first (970-1,640 chars) | **0 of 10** |
| Strata's prefill appended: no thinking | **6 of 10** |

So the refusals come from the prefill, not from Strata's engine or the file. The speed numbers above stand (they
count every output token, thinking included), but Strata's answers at effort 0 are worse than llama.cpp's until
that prefill goes.

## Pitfalls

* **Strata drops `temperature: 0`.** `serve/server.py` `sampling_keys()` sends a temperature only when it is above
  0, so a greedy request runs at the engine's default (the model card's 1.0). Strata's text varied between
  repetitions; llama.cpp's did not.
* **Setup left the DSpark drafter out.** With `--gguf-dir` the config said `"drafting": "dspark"` but its args had no
  `--dspark`; it was added by hand. The `-nodraft` configs add `--draft off`.
* **Strata 0.2.20 moved everything into `terminal/`** (engine, configs, run scripts, `.venv`), and `update.sh` is
  gone (`git pull` + `./setup.sh --update`). `switch-model.sh` and `update-engines.sh` follow the new layout.
