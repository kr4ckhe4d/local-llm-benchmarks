# Strata — Qwen3.8-Flash-Next on its own engine

[Strata](https://github.com/Niko1221/Strata) is a separate inference engine
built only for Qwen3.8-Flash-Next (parts of ggml, its own expert cache, MTP
draft layer and server). It keeps the hottest experts on the GPUs, the rest
in RAM, and the per-layer n-gram table on the SSD. It serves OpenAI and
Anthropic APIs, so Claude Code talks to it directly.

Tried 2026-10-10 on the two cards (R9700 + 9070 XT), Strata 0.1.41 (commit
`fb58e0d`), engine compiled by `setup.sh` against the system ROCm 7.2.4.

## Coder IQ1_M — tried 2026-10-22, deleted

**Why the switch:** IQ3_XXS logged the desktop out twice on 2026-10-22. The
kernel OOM killer took `kwin_wayland` (13:13 and 13:30). `--resident-experts`
sizes its RAM copy from `MemAvailable` at start, minus
`STRATA_RESIDENT_HEADROOM_GIB` (default 4). It held 15.8 GiB of experts,
pageable (`STRATA_RESIDENT_PIN=0`), so most of it went to zram. With ~8 GB of
GTT and Blender and Chrome on top, the 30 GB box ran out. The OOM killer chose
`strata` first but could not reap it (GPU-mapped memory), so it went on
through Chrome, Blender and plasmashell to kwin.

[Coder](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-Coder-GGUF)
keeps 256 of each layer's 512 experts, stored like IQ3_S. "IQ1_M" is 1.89
bits per *original* parameter, not the storage format. Shard 2 is the same
file as IQ3_XXS's, so setup hard-linked it: deleting `models/IQ3_XXS` does
not delete the Coder's copy.

```bash
./setup.sh --setup --yes --backend hip --family coder --model IQ1_M --gpus 1,0 \
  --context 204800 --port 8095 --host 0.0.0.0 --api-key <key> \
  --data-dir /mnt/fast/strata-data --no-start
```

Then re-apply the args that setup drops in `strata-coder-iq1_m.json`:
`--pipeline-windows 2`, `STRATA_STAGE_TRIM=1`, `before_load`,
`idle_unload_s`, `lazy_load`, plus **`STRATA_RESIDENT_HEADROOM_GIB=10`**.
`layer_split` stays `auto` (layers 0-26 / 27-47); the 33 was tuned for
IQ3_XXS.

| | IQ3_XXS | Coder IQ1_M |
|---|---|---|
| Experts on the cards | 22,143 of 24,576 | 11,951 of 12,288 |
| Decode hit rate | 97.1-98.7% | 98.3-99.9% |
| Experts in RAM / Strata RSS | 15.8 GiB / OOM | 7.1 GiB / 10.6 GB |
| RAM still free, model loaded | none | 16.2 GB at the lowest |
| First load | 1-3 min | ~20 s |
| Short code answer | 102.1 tok/s (94.8 tuned, long) | 122.6-132.8 tok/s |
| Long answer, thinking medium | — | 96-104 tok/s over 10-17K tokens |
| Code quality, thinking off | **43/50**, 4/7 clean | 42/50, 3/7 clean |
| Code quality, thinking medium (3 runs) | **47, 47, 47** /50 | 31, 43, 39 /50 (mean 37.7) |

Code quality results are in
[`qwen3.8-flash-next-coder-IQ1_M-strata`](benchmarks/qwen3.8-flash-next-coder-IQ1_M-strata).

* **Thinking off is a wash.** It gets `glob_match` 8/8, where IQ3_XXS got
  4/8. It loses 3 on `shlex_split` quoting, and one each on `urljoin`
  (`dot_only`) and `parse_qsl` (`empty`).
* **At medium effort IQ3_XXS is clearly better (repeated 2026-10-22).** It
  scored 47/50 in all three runs, with the same three misses every time.
  The Coder scored 31, 43 and 39. `urljoin` is the Coder's weak task (0, 5,
  3 of 9, against 9/9 every time). Run 1 also lost `csv_rows` to an endless
  loop (`i += 1` missing in its `\n` branch); runs 2 and 3 got it 7/7.
  Results are in `code-quality-thinking-medium-run{2,3}.txt` in both
  folders.
* **IQ3_XXS fits with `STRATA_RESIDENT_HEADROOM_GIB=12`.** It held 13.75 GiB
  of experts in RAM (15.8 at the default 4). The lowest free RAM was 9.2 GB,
  with Chrome open and Blender closed. It also ran 107-114 tok/s, faster
  than the 81-102 measured before. So the OOM came from the headroom, not
  the model size. With Blender open it is still tight.
* It thinks longer at medium than IQ3_XXS did: 1.2-17K tokens per task, 9
  minutes for the suite against 7.

**Verdict: deleted, back to IQ3_XXS.** The Coder's only gain was RAM, and
the 12 GiB headroom fixed that for IQ3_XXS without giving up 9 checks at
medium effort. `strata-iq3_xxs.json` carries the headroom, and
`switch-model.sh` starts `run-iq3_xxs.sh` again. The old config without it
is `strata-iq3_xxs.json.pre-headroom` in the Strata folder.

## IQ3_XXS — the one to use (with `STRATA_RESIDENT_HEADROOM_GIB=12`)

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

### Tuned, 2026-10-12

`--pipeline-windows 2` plus `STRATA_STAGE_TRIM=1` (`"layer_split": "33"`):
generation 80.7 -> **94.8 tok/s** (+17.5%; code 125-143, prose 73-78), prompt
reading 1,700 -> 1,653 tok/s on a 29K prompt. Seven other settings measured;
see [benchmarks/strata-tuning/](benchmarks/strata-tuning/README.md). A
`setup.sh --setup` run drops the args entry and the explicit split: re-apply.

### 200K context

`--context 204800` (setup's 200K step, inside the trained 262,144, no rope
scaling): the cards still hold 21,713 pairs, ~99.6% of the routed mass, and
the short code answer runs 96.3 tok/s against 102.1 at 128K. KV is int8, about
0.9 GB per 64K tokens. 256K should fit too; 384K/512K are experimental.

### Code quality: the best score here, but not at xhigh (2026-10-18)

`code-quality-test.py` against Strata v0.1.43 (`7695859a`) on :8095. The
harness now takes `--api-key-env` and sends Strata's key as a bearer token.
Results in
[`qwen3.8-flash-next-IQ3_XXS-strata`](benchmarks/qwen3.8-flash-next-IQ3_XXS-strata):

| Setting | Checks | Clean tasks | Thinking tokens | Time |
|---|---|---|---|---|
| Thinking off, temp 0.0 | **43/50 (86%)** | 4/7 | none | ~1 min |
| Thinking, **medium**, temp 0.6 | **47/50 (94%)** | 5/7 | 46K (1.6-14.3K per task) | 7 min |
| Thinking, xhigh (default), temp 0.0 | glob_match 0/8, stopped | | 100K, no answer | 9.4 min on one task |
| Thinking, xhigh (default), temp 0.6 | stopped during glob_match | | 70K, no answer | 11.4 min on one task |

* **Both are the top scores in this repo.** Thinking off it beats every other
  model's 39/50 by 4 checks, and it is the only model to get `urljoin` 9/9.
  Medium misses only `shlex_split`'s `dq_escapes` and `textwrap`'s
  `collapse` and `random60`, which every model misses.
* **Never ask it at the default effort.** With thinking on and no effort,
  the template picks xhigh. There it deliberates on `glob_match`'s
  bracket edge cases without end: 100K tokens with greedy decoding, still
  going at 70K with temperature 0.6. With `reasoning_effort` medium or low
  the same bare prompt solved it 8/8 in ~6K tokens and under a minute. So
  did the same question asked through a client with a 10K-token agent
  prompt (2K tokens, 31 s). Pass `--reasoning-effort medium` (also new in
  the harness) and say which effort a score used. This is not the web
  chat's High setting, which maps to xhigh too; the API defaults there when
  `enable_thinking` is true and no effort is given.
* The medium row is one sample at temperature 0.6, so allow a check or
  two of spread. The xhigh runs are kept as
  `code-quality-thinking-temp0-loop.txt` and
  `code-quality-thinking-xhigh-temp06-stopped.txt`.

## Beside the router

The llama.cpp router cannot hold Strata: it only spawns `llama-server`
children and talks to them over a command pipe. So Strata runs next to it on
port 8095, and the two take turns on the cards (Strata IQ3_XXS fills ~32 + ~16
GB; nothing else fits beside it):

* **Strata to router:** `"idle_unload_s": 900` in `strata-iq3_xxs.json`
  unloads Strata after 15 idle minutes, the same as the router's
  `--sleep-idle-seconds`.
* **Router to Strata:** `"before_load":
  ".../strata-before-load.sh"` unloads every loaded router model before Strata
  loads again, and waits for them to exit.
* **Claude Code:** `claude-local.sh strata` uses Strata's URL, key and
  `/health` context. Any router preset first asks Strata to unload
  (`POST /v1/unload` with the key). The key goes in
  `~/.config/strata/api-key` on the laptop, or `STRATA_API_KEY`.
* **Pi:** `pi-local.sh strata`, or `pi-local.sh <preset>` for the router, the
  same unload rules as `claude-local.sh`. It writes two providers into Pi's
  `~/.pi/agent/models.json`, `cachypc` (every router preset of 32K or more)
  and `strata` (key as `!cat ~/.config/strata/api-key`, never the literal),
  and leaves the file's other providers alone. Pi's own llama.cpp provider was
  not used: it lists router models only after an interactive `/login`. Pi's
  system prompt is ~2.5K tokens, so its first turn reads in under 3 s.
* **Open WebUI:** add a second OpenAI connection, `http://CachyPC.local:8095/v1`
  with the key. Open WebUI cannot unload Strata before a router model, so a
  router model picked there while Strata is loaded will not fit: unload
  Strata from its web page first, or wait out the idle timer.

`switch-model.sh router` starts Strata too (`switch-model.sh strata` starts it
alone), with `"lazy_load": true`: the API is up at once and the model loads on
the first request, so a reboot plus that one command restores both.

`setup.sh --setup` keeps these keys (`carry_over` keeps top-level keys it does
not write).

Claude Code through `claude-local.sh strata`: a one-shot (write `fib.py`, run
it) was correct in 24 s, reading the 21K-token first prompt at 1,358 tok/s;
later turns reused it and wrote at 80-99 tok/s.

Testing it from a Claude Code session on the box itself gave `401 missing or
wrong API key`: the nested `claude` inherits the desktop app's sign-in, which
takes precedence over `ANTHROPIC_AUTH_TOKEN`. Under `env -i` it worked; a
plain terminal is fine.

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
