# Expert "modes" on Strata

Can a model's expert cache be switched per task, a "coder" or "writer" mode,
instead of one general ranking? Measured 2026-10-12 on Qwen3.8-Flash-Next
IQ3_XXS under Strata 0.1.41 ([strata.md](../../strata.md)), 32K context.

**Verdict: yes as a starting point, when the cache cannot hold every expert; per-request switching adds little on top of Strata's adaptive tier.** A
profile built from the task's own routing put 96-99% of expert lookups in
VRAM, against 48-73% for Strata's shipped general profile, and generated
24-42% faster. The wrong profile costs 5-17% against the general one.

## Method

`run.py`, prompts in `prompts.json` (3 domains x 8 train / 6 test prompts,
written for this run; train and test prompts are different).

1. **Trace.** Serve each domain's train prompts on both cards with
   `--dump-routing`: the routed experts of every layer and position. Where an
   expert sits does not change which one the router picks.
2. **Build.** `tools/make_profile.py TRACE --no-base`: every (layer, expert)
   pair ranked by how often that domain routed it.
3. **Eval.** The R9700 alone (15,764 cache slots, 25.6 GiB: 64% of the
   24,576 pairs; 17.7 GiB more in RAM, the rest on the SSD). Each profile
   seeds the cache, `--adapt-every 100000` keeps it there (the profile alone
   decides residency), and every test prompt runs at temperature 0,
   thinking off, 400 tokens max. Hit rate and tok/s from the engine log, per
   request.

The 9070 XT alone (16 GB, ~24% of the pairs) was the first choice and was
dropped: with 22 GB of experts resident in 30 GB of RAM the CPU pool stalled
(0.5 tok/s) and the engine's watchdog stopped it.

## Routing overlap (traces)

Share of each domain's routing that the top 6,000 pairs of a profile cover.
A random 6,000 of 24,576 would cover ~24%.

| profile \ routing of | code | writing | chinese |
|---|---|---|---|
| code | **76.3%** | 15.4% | 12.0% |
| writing | 15.0% | **81.0%** | 52.6% |
| chinese | 13.9% | 57.4% | **85.7%** |

Code and prose use different experts: their top-6,000 sets share 17%, and
each covers the other *worse* than a random pick. English and Chinese prose
share 61%.

## Hit rate and speed (eval)

Decode VRAM hit rate / generation tok/s, 6 prompts each (~2,100-2,400 tokens).

| cache seeded from \ prompts | code | writing | chinese |
|---|---|---|---|
| shipped (general) | 73.4% / 94.0 | 63.0% / 63.8 | 47.6% / 52.8 |
| code | **95.6% / 116.1** | 51.3% / 55.7 | 40.6% / 50.5 |
| writing | 53.5% / 78.1 | **98.6% / 80.4** | 77.3% / 64.0 |
| chinese | 55.4% / 78.8 | 87.0% / 73.6 | **98.9% / 75.2** |

* Matched against shipped: code +24%, writing +26%, Chinese +42%.
* Mismatched against shipped: code profile on prose -13% / -4%, prose
  profiles on code -16% / -17%.
* Compare within a column. Code is faster at any hit rate because its MTP
  drafts are accepted more often, so 116 tok/s at 95.6% and 80 at 98.6% are
  not in conflict.
* Per-prompt spread is small (±5-10% within an arm); one run per arm.
* SSD reads stayed under 1 GB per arm: the misses came from RAM.

## Per-request switching: the adaptive tier already does most of it

`run.py adapt`: Strata's defaults (adaptive tier on: up to 96 swaps every 4
windows, RAM to VRAM with no file reads). Start from one domain's profile,
serve the other domain's 6 test prompts, then the first's. Hit rate / tok/s
per request:

| | 1st | 2nd | 3rd | 4th | 5th | 6th |
|---|---|---|---|---|---|---|
| code cache, writing prompts | 94% / 68 | 98% / 72 | 99% / 81 | 97% / 79 | 99% / 83 | 99% / 78 |
| then code prompts | 87% / 97 | 95% / 107 | 97% / 111 | 96% / 109 | 96% / 97 | 97% / 117 |
| writing cache, code prompts | 87% / 90 | 95% / 107 | 97% / 109 | 96% / 108 | 96% / 97 | 97% / 113 |
| then writing prompts | 94% / 72 | 98% / 74 | 99% / 76 | 96% / 79 | 99% / 83 | 99% / 77 |

Within the **first** 400-token request after a domain change the hit rate is
back to 87-94% (51-54% with the cache frozen), and by the second it matches
the domain's own profile. The only loss is that first request: 68-72 tok/s
against ~80 on writing, 90-97 against ~116 on code.

A switch moves 2,900-5,500 of the 15,764 cached experts (5-10 GB, 1-2 s over
PCIe; `profile-*.bin` top-15,764 sets compared). An explicit `MODE <profile>`
command would fit Strata's design: the adaptive tier picks its swaps from
per-expert routing counts (`a_usage` in `src/program/generate.cpp`), so
overwriting those with a mode's profile and running rounds back to back
between requests would reuse the existing exchange code. On this setup it
would gain only on the first request after a change, ~15-25% speed for a few
seconds. **Not built.** It matters more where adaptation lags: smaller
caches, short requests, and a cold start (a mode seed against the shipped
profile is the static table above).

## Not tested

* **Mixed work.** An agent session is code plus English plus tool JSON.
  A blended profile, or switching per request, was not tried.
* **Smaller caches.** At 24% (a 16 GB card) the effect should be larger, but
  that configuration stalled here.
* **A hard filter** (experts switched off): only the soft version, where
  every expert stays reachable from RAM, was measured. Answers are the same
  model's in every arm.
