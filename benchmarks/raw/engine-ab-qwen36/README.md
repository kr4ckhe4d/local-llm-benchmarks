# Qwen3.6-35B-A3B: llama.cpp against Strata (2026-11-15)

Same files for both engines: Unsloth's `Qwen3.6-35B-A3B-MTP-GGUF` (UD-Q6_K_XL, UD-Q4_K_XL), downloaded by
Strata's setup into `/mnt/fast/strata-data/models/`. 128K context everywhere.

* **llama.cpp** 4b77dee05 (ROCm), both cards, the removed `qwen3.6-35B-A3B-q6-128k` preset's flags
  (`-ub 1024 -b 2048 -fa on -ctk q8_0 -ctv q8_0 -lm dio`), with and without `--spec-type draft-mtp`.
* **Strata** 13eedf55 (engine 0.1.59.1), its own `src/qwen35` path, R9700 alone (that engine has no
  multi-GPU split), setup's config (`--prefill auto --mtp 2`).

Client: [`../../engine-ab.py`](../../engine-ab.py), OpenAI chat API, streaming, timed on the client.
Greedy, thinking off, penalties sent as off. Output tokens are counted with `llama-tokenize` on the same GGUF
for both engines. Decode = (tokens - 1) / (last token - first token). Prefill = prompt tokens / time to first
token. Three generation prompts (code, prose, explain; up to 1,024 tokens) x 3 repetitions, and wikitext cut
to 32,000 and 120,000 tokens (`docs/`) + a summary question, 256 tokens out, 2 repetitions, with a nonce in
the first line so no prefix cache applies. Medians. Runs: `run.sh`, `run-q6-32k.sh`; rows in `results.jsonl`.

## Results (tok/s)

| Arm | Code | Prose | Explain | 32K prefill | 32K decode | 120K prefill | 120K decode | Peak VRAM R9700 + 9070 XT |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| llama.cpp Q6, 2 cards | 76.6 | 76.6 | 76.5 | **5,197** | 61.5 | **3,220** | 39.2 | 22.5 + 13.2 GB |
| llama.cpp Q6 + MTP, 2 cards | 153.4 | 102.2 | 124.7 | 4,013 | 107.3 | 2,420 | 72.3 | 25.1 + 13.3 GB |
| llama.cpp Q4 + MTP, 2 cards | 164.1 | 109.4 | 136.4 | 3,744 | **110.1** | 2,556 | **78.4** | 19.0 + 10.1 GB |
| Strata Q4 + MTP, R9700 | **204.7** | **159.4** | **177.1** | 1,046 | 50.2 | 376 | 10.2 | 31.8 + 0.7 GB |
| Strata Q6, R9700 | did not load | | | | | | | |

Spread across the 3 repetitions is under 1.5% for every generation cell. Strata's own log line agrees
with the client (32K: 1,046 tok/s prompt, 50.0 tok/s decode, drafts accepted 76 of 102).

## What it says

* **Short context: Strata wins.** In an empty context Strata Q4 is 25-46% faster than llama.cpp Q4 with
  the same MTP layer, and 2.1-2.7x the old no-MTP Q6 preset. It does that on the R9700 alone; the
  9070 XT stays free.
* **Long context: llama.cpp wins by a wide margin.** At 32K Strata reads prompts 3.6x slower and decodes
  2.2x slower; at 120K, 6.8x and 7.7x slower: a 120K prompt takes 319 s against 46 s, and the answer
  comes at 10 tok/s against 78. At a 128K context Strata uses its smallest prompt chunk (512; its log:
  `context 131072 cells, prompt chunk 512`) and keeps fp32 K/V. Its published Qwen3.6 numbers are
  pp4096 and tg128 in an empty context, which this run reproduces (`docs/QWEN36.md`: 117.8 plain,
  ~184 with MTP).
* **Strata Q6 does not fit this box.** At 128K, and again at 32K, the Q6 experts (about 28 GiB) do not
  fit the R9700 beside the engine's buffers (24.4 GiB free at 32K). Strata then keeps a copy of every expert
  in system RAM; with 31 GB it went 27 GB into swap and was still loading after 9 minutes. Setup warns of
  this ("UD-Q6_K_XL needs about 44 GB of RAM").
* **llama.cpp should use the MTP file.** The Unsloth MTP GGUF with `--spec-type draft-mtp` lifts llama.cpp
  from 76.5 to 102-153 tok/s in an empty context and from 39 to 72 at 120K, for a 25% slower prompt read.

## Pitfall: Strata's model-card sampling switches MTP off

Strata's server fills whatever a request leaves out from the model card (`MODEL_CARD_SAMPLING` in
`serve/server.py`; Qwen3.6 instruct: presence_penalty 1.5). Any penalty makes the engine sample token by
token (`needs_logits()` in `include/strata/qwen35/sampling.hpp`), so a request with only `temperature: 0`
decoded without drafts and with a penalty: 122 tok/s (`results-invalid-strata-q4-penalty.jsonl`) instead of
205. Clients that want Strata's MTP speed must send `presence_penalty: 0` (or set it in the config's
`sampling` block).
