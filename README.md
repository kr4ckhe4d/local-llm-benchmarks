# Local LLM Benchmarks — CachyPC

**Hardware:** AMD Ryzen 9 5950X (16C/32T) · AMD RX 9070 XT (16GB VRAM, RDNA4) ·
64GB DDR4-3200 dual-channel · `llama.cpp` b8918, Vulkan backend, at
`~/llama.cpp/build-vulkan/bin/`. Switching script: `~/llama.cpp/switch-model.sh`.

## Comparison benchmarks

| Model | Total params | Active params | Type | Quant | File size |
|---|---|---|---|---|---|
| Qwen2.5-Coder-14B-Instruct *(deleted)* | 14B | 14B | Dense | Q4_K_M | 8.4GB |
| Qwen2.5-Coder-14B-Instruct *(deleted)* | 14B | 14B | Dense | Q8_0 | 14.6GB |
| GPT-OSS-20B | 21B | ~3.6B | MoE | MXFP4 | 11.3GB |
| Qwen2.5-Coder-32B-Instruct *(deleted)* | 32B | 32B | Dense | Q4_K_M | ~19GB |
| GPT-OSS-120B *(deleted — freed space for Qwen3-Coder-Next)* | 117B | ~5.1B | MoE | MXFP4 | 59.0GB |
| Qwen3.6-35B-A3B | 35B | ~3B | MoE | UD-Q4_K_M | 20.6GB |
| Gemma 4-26B-A4B | 25.2B | ~3.8B | MoE (30 layers) | UD-Q4_K_M | 15.8GB |
| Qwen3-Coder-Next | 80B | ~3B | MoE (48 layers, hybrid attn) | UD-Q4_K_M | 49.3GB |

### Throughput by context length

| Model | Context | Config | VRAM used | Free | Host RAM | Prompt tok/s | Gen tok/s |
|---|---|---|---|---|---|---|---|
| Qwen2.5-Coder-14B Q4_K_M *(deleted)* | 4K | `-ngl 99` | fits fully | — | 0 | — | 61.5 |
| Qwen2.5-Coder-14B Q8_0 *(deleted)* | 16K | `-ngl 99 -fa on -ctk q8_0 -ctv q8_0` | fits (355MB free) | 355 | 0 | — | 39.0 |
| Qwen2.5-Coder-32B *(deleted)* | 4K | any `-ngl` split | n/a — CPU-bandwidth-bound | — | large | — | 5–7 |
| GPT-OSS-20B | 4K | `-ngl 99` | 11,918 / 16,304 | 4,386 | 0 | 1078.8 | 173.4 |
| GPT-OSS-20B | 32K | `-ngl 99` | 12,591 / 16,304 | 3,714 | 0 | 818.9 | 180.5 |
| GPT-OSS-20B | 128K | `-ngl 99` | 14,900 / 16,304 | 1,402 | 0 | 979.4 | 181.0 |
| GPT-OSS-20B | 256K | `-ngl 99 -fa on -ctk q8_0 -ctv q8_0` | 15,464 / 16,304 | 840 | 0 | 961.0 | 171.1 |
| GPT-OSS-20B | 512K | `-ngl 99 -ncmoe 9 -fa on -ctk q8_0 -ctv q8_0` | 15,863 / 16,304 | 441 | 4.5GB | 150.0 | 44.9 |
| GPT-OSS-20B | 1M | `-ngl 99 -ncmoe 24 -fa on -ctk q4_0 -ctv q4_0` | 11,338 / 16,304 | 4,966 | 12.9GB | 71.8 | 24.1 |
| GPT-OSS-120B | 4K | `-ngl 99 -ncmoe 28` | 15,789 / 16,304 | 515 | 46.7GB | 26.9 | 19.8 |
| GPT-OSS-120B | 32K | `-ngl 99 -ncmoe 29` | 15,253 / 16,304 | 1,051 | 48.4GB | 26.5 | 19.4 |
| GPT-OSS-120B | 128K | `-ngl 99 -ncmoe 31` | 15,738 / 16,304 | 566 | 51.9GB | 24.7 | 18.7 |
| Qwen3.6-35B-A3B | 4K | `-ngl 99 -ncmoe 12` | 16,156 / 16,304 | 148 | 6.5GB | 131.1 | 48.1 |
| Qwen3.6-35B-A3B | 32K | `-ngl 99 -ncmoe 14` | 15,817 / 16,304 | 487 | 7.6GB | 126.4 | 45.9 |
| Qwen3.6-35B-A3B | 128K | `-ngl 99 -ncmoe 18` | 15,879 / 16,304 | 425 | 9.8GB | 115.1 | 41.2 |
| Qwen3.6-35B-A3B | 256K | `-ngl 99 -ncmoe 18 -fa on -ctk q8_0 -ctv q8_0` | 16,003 / 16,304 | 301 | 9.5GB | 83.8 | 30.6 |
| Qwen3.6-35B-A3B | 512K | `-ngl 99 -ncmoe 25 -fa on -ctk q8_0 -ctv q8_0` | 16,092 / 16,304 | 212 | 13.1GB | 94.0 | 34.8 |
| Qwen3.6-35B-A3B | 1M | `-ngl 99 -ncmoe 42 -fa on -ctk q8_0 -ctv q8_0` | 16,111 / 16,304 | 193 | 20.7GB | 75.3 | 28.8 |
| Qwen3-Coder-Next | 4K | `-ngl 99 -ncmoe 35` | 15,273 / 16,304 | 1,031 | 34.2GB | 62.6 | 26.4 |
| Qwen3-Coder-Next | 32K | `-ngl 99 -ncmoe 35` | 15,999 / 16,304 | 305 | 34.3GB | 64.0 | 26.4 |
| Gemma 4-26B-A4B | 4K | `-ngl 99 -ncmoe 3` | 15,689 / 16,304 | 142 | 2.2GB | 256.4 | 69.2 |
| Gemma 4-26B-A4B | 32K | `-ngl 99 -ncmoe 5` | 15,813 / 16,304 | 491 | 3.3GB | 208.2 | 53.6 |
| Gemma 4-26B-A4B | 128K | `-ngl 99 -ncmoe 8` | 15,924 / 16,304 | 380 | 4.8GB | 139.2 | 43.7 |
| Gemma 4-26B-A4B | 256K (max) | `-ngl 99 -ncmoe 16` | 15,748 / 16,304 | 556 | 8.9GB | 122.6 | 35.1 |

Notes: GPT-OSS-120B not tested beyond 128K (and since deleted). Gemma 4's
context hard-caps at 256K (no extended range). GPT-OSS-20B's official max is
128K — 256K/512K/1M are unsupported territory, numbers only, not a quality
claim. All configs above use a safety margin over the absolute tightest
`-ncmoe` found, not the razor-thin ceiling. Qwen3-Coder-Next is Qwen's actual
coding-specialist model this generation (not literally named "3.6-Coder") —
slower in raw tok/s than Qwen3.6-35B-A3B (2.3x the total size means far more
host RAM traffic), but on a real coding prompt it answered directly with no
chain-of-thought preamble (unlike Qwen3.6), producing correct code faster in
practice despite the lower tok/s.

## Commands

One-shot CLI test (swap in the model/config from the table above):

```bash
./build-vulkan/bin/llama-cli -m models/<file>.gguf -ngl 99 [-ncmoe N] \
  [-fa on -ctk q8_0 -ctv q8_0] -c <context> -st -p '<prompt>' -n 300 < /dev/null
```

Persistent server (OpenAI-compatible API, reachable on the LAN):

```bash
nohup ./build-vulkan/bin/llama-server -m models/<file>.gguf -ngl 99 [-ncmoe N] \
  [-fa on -ctk q8_0 -ctv q8_0] -c <context> -np 1 --host 0.0.0.0 --port 8090 \
  > /tmp/llama-server.log 2>&1 < /dev/null &
disown
```

```bash
curl -s http://192.168.4.228:8090/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"<name>","messages":[{"role":"user","content":"<prompt>"}],"max_tokens":300}'
```

## How to switch models

Use the script — it has every config above baked in, and refuses combos that
were never benchmarked instead of guessing:

```bash
~/llama.cpp/switch-model.sh <model> <context>   # gpt-oss-20b|gpt-oss-120b|qwen3.6|gemma4 × 4k|32k|128k|256k|512k|1m
~/llama.cpp/switch-model.sh status              # what's running now
~/llama.cpp/switch-model.sh list                # tested combinations
```

Manual fallback (what the script does under the hood) — there's no hot-swap,
one `llama-server` process holds one model, and clients can't switch it by
changing the `"model"` field in a request:

```bash
pkill -f 'llama-server|llama-cli'; sleep 2
# then the persistent-server command above with the new model/config
# then poll /health until 200 before sending real requests
```
