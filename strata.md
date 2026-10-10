# Strata — Qwen3.8-Flash-Next on its own engine

[Strata](https://github.com/Niko1221/Strata) is a separate inference engine
built only for Qwen3.8-Flash-Next (parts of ggml, its own expert cache, MTP
draft layer and server). It keeps the hottest experts on the GPUs, the rest
in RAM, and the per-layer n-gram table on the SSD. It serves OpenAI and
Anthropic APIs, so Claude Code talks to it directly.

Tried 2026-10-10 on the two cards (R9700 + 9070 XT), Strata 0.1.41 (commit
`fb58e0d`), engine compiled by `setup.sh` against the system ROCm 7.2.4.

## IQ3_XXS — the one to use

**Verdict: kept.** Same prompt and settings as the Q2_0 test below, and the
output was "day and night, heaps better": a ginger cat crossing a farm fence
with a two-joint walk cycle, stride matched to the fence speed, and five
parallax layers. It also took far longer: 462 s of thinking, 53,815 tokens
in 661 s.

```bash
./setup.sh --setup --yes --backend hip --family qwen --model IQ3_XXS --gpus 1,0 \
  --context 131072 --port 8095 --host 0.0.0.0 --api-key <key> \
  --data-dir /mnt/fast/strata-data --no-start
```

| | Q2_0 | IQ3_XXS |
|---|---|---|
| Disk | 66 GB + 38 GB pack | 71 GB + 42 GB low-RAM experts file |
| Experts on the cards (128K) | 24,420 of 24,576 pairs | 22,143 of 24,576, ~99.7% of the routed mass; 35.0 GB |
| VRAM hit rate per request | 99.5-99.8% | 97.1-98.7% |
| VRAM (R9700 / 9070 XT) | 31.1 / 16.2 GB | 31.9 / 16.1 GB |
| RAM used | ~7 GB | ~11-12 GB |
| Short code answer, thinking off | 115.8 tok/s | 102.1 tok/s |
| Long answer, thinking High | 86.5 tok/s over 13K tokens | 81.4 tok/s over 54K tokens |
| MTP drafts accepted (short answer) | 87% | 82% |

IQ3_XXS costs 6-12% of the speed for the quality jump. Strata's NVIDIA table
had it at two thirds of Q2_0. Here the two cards hold nearly all of its
experts, so the CPU barely works.

## Q2_0 — fast, same quality as before

**Verdict: not kept.** Same `ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF`
Q2_0 file as the [llama.cpp run of 2026-10-06](gsq-rco.md#qwen38-flash-next-gsq-rco-q2_0).
Strata fixed the speed, not the weights: in hands-on use the output was still
worse than Qwen3.8-27B Q8_0. Model and pack deleted for IQ3_XXS (above).

The hands-on test was Strata's web chat at its defaults: thinking High,
temperature 0.6, top-p 0.95, top-k 20, no max tokens. Prompt: "create me an
animated svg of a cat walking on a fence". It thought for 141.8 s and wrote
13,324 tokens in 155 s (86.5 tok/s, 99.8% VRAM hit rate). So the gap to Q8 is
not a thinking budget being cut short, as it might have been on 2026-10-06.

Setup line (the box's 30 GB of RAM puts it in Strata's low-RAM mode):

```bash
./setup.sh --yes --backend hip --family qwen --model Q2_0 --gpus 1,0 \
  --context 131072 --port 8095 --data-dir /mnt/fast/strata-data --no-start
```

`--gpus 1,0` is the R9700 first: setup numbers the 9070 XT as GPU 0.

| | |
|---|---|
| Disk | 66 GB download + 38 GB AVX-512 expert pack + 6.5 GB MTP layer |
| Load | ~30 s warm |
| Layer split | auto, K=33: layers 0-32 on the R9700, 33-47 on the 9070 XT |
| Experts on the cards | 24,576 of 24,576 profiled pairs at 64K; 24,420 at 128K |
| VRAM | 31.1 / 32.6 GB and 16.2 / 16.3 GB |
| RAM | ~7 GB used; KV streaming off (setup: not enough RAM) |
| Generation | **112-116 tok/s** on short answers, MTP drafts accepted 75-94%; 86.5 tok/s over a 13K-token answer |
| Prefill | **1,864 tok/s** on a 34.7K prompt; 1,369 tok/s on 5.3K |
| Follow-up turns | prefix reused, new tokens only, under 0.4 s |

Generation is about twice the fastest Qwen3.8 preset (IQ4_XS + MTP, 71 tok/s).
The publisher's scores explain the quality: 89.07 task average for Q2_0
against 93.12 for BF16, LiveCodeBench v6 81 against 87.

### Claude Code

A Messages API tool-call probe returned a correct `tool_use` in 1.8 s. A
Claude Code one-shot (write `fib.py`, run it) was correct in 32 s wall, 18.6 s
of it reading the 34.7K-token first prompt.

Launch it the way `claude-local.sh` does: `--strict-mcp-config` with no account
MCP servers, all four model slots set to one name (Strata ignores the name),
`ANTHROPIC_BASE_URL=http://<box>:8095`, `ANTHROPIC_AUTH_TOKEN=<key>`.

### Gotchas

1. **Setup's default context is 64K**, which Claude Code cannot use: its first
   request (~50K with the account MCP servers) plus the default 32K
   `max_tokens` is refused (`requests are never truncated`). Set `--context
   131072`. At 128K the cards still hold ~100% of the experts.
2. **Port.** Strata's default 8080 is taken on this box, and the router's
   8090 was free only because the router was down when setup ran. When it came
   back, Strata's `server.py` exited at once, and a `/health` poll got the
   router's `{"status":"ok"}`. Use 8095 and check for `"service": "strata"`.
3. **LAN access needs a key.** `--host 0.0.0.0 --api-key <key>`; the web app
   then asks for it under About > Settings. Without the key: 401.
4. **Thinking defaults to High** ("thorough"). The web chat's Sampling panel
   and `reasoning_effort` can set it lower; note which level a quality
   comparison used. The panel's settings apply to API clients only with "Use
   for other apps too" on.
