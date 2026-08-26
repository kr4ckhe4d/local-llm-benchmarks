# Instella-MoE-16B-A3B-Think — CachyPC

Measured 2026-08-26 on the RX 9070 XT (gfx1201, RDNA4, 16,304 MiB) described in
[README.md](README.md).

**Both the GGUF and the fork build were deleted from disk same day** — the
model file (`~/llama.cpp/models/Instella-MoE-16B-A3B-Think-Q4_K_M.gguf`,
10.47GB) and the `~/llama-instella/` build tree (1.2GB). Kept here because the
measurements below stand; nothing in this section changes if it's
re-downloaded. Re-cloning the fork and re-pulling the GGUF (see Build and The
model, below) reproduces this exactly.

**Verdict up front: not usable here yet, and not for a quality reason.** The
only fork that loads this architecture at all does not wire up reasoning-content
splitting for it. `enable_thinking:false` and `--reasoning-budget` — the two
controls that tame every other thinking model in this repo (Qwen3.8, Nemotron,
Muse Glimmer, Laguna) — are both silent no-ops here. Chain-of-thought floods
straight into `content` with no cap, so every probe with a realistic
`max_tokens` gets cut off mid-reasoning before producing an answer. The model's
actual coding ability was not measurable this session.

---

## The model

`DevQuasar/amd.Instella-MoE-16B-A3B-Think-GGUF`, `Q4_K_M`, base model
`amd/Instella-MoE-16B-A3B-Think`. Arch string in the GGUF is `instella-moe`, MoE
with ~15.86B total params (`~16B` in the name), native `context_length: 32768`.
File: `Instella-MoE-16B-A3B-Think-Q4_K_M.gguf`, 10,470,249,600 bytes (~9.75 GiB).

## Why a fork was needed

Mainline llama.cpp has no `instella-moe` support — attempting to load it on the
`build/` tree used everywhere else in this repo fails immediately:

```
E llama_model_load: error loading model: unknown model architecture: 'instella-moe'
```

There is an open upstream feature request
([ggml-org/llama.cpp#12270](https://github.com/ggml-org/llama.cpp/issues/12270))
for the related `InstellaForCausalLM`, unmerged. The only implementation found
is a community fork:
[`csabakecskemeti/llama.cpp`](https://github.com/csabakecskemeti/llama.cpp),
branch `instella-moe`.

**This fork is a much smaller bet than the TurboQuant one** (see
[turboquant.md](turboquant.md)). Where TurboQuant's fork was 165 commits behind
its own upstream at time of test, this branch is rebased directly onto a recent
mainline point (`bb4caa7`, "bump version to 0.2.0", 2026-08-21) with exactly
four commits on top:

```
7a3c74e rebase
f9bc325 add instella-moe to the blocklist of llm_arch_supports_sm_tensor
0f2123f instella-moe: extra comments from Opus5 to help highlight the 2 deltas
        compared to deepseek2
8f9a746 Add new InstellaMoEForCausalLM arch
```

That last commit message is the tell for what happened later in this file: the
architecture was ported by diffing against `deepseek2`, and — as the tool-call
and reasoning results below show — not everything in that diff carried over.

## Build

Same recipe as the ROCm build in README.md, different tree — this does **not**
touch `~/llama.cpp`:

```bash
git clone --depth 50 --branch instella-moe \
  https://github.com/csabakecskemeti/llama.cpp.git ~/llama-instella
cd ~/llama-instella
HIPCXX="$(hipconfig -l)/clang" HIP_PATH="$(hipconfig -R)" \
  cmake -B build -DGGML_HIP=ON -DAMDGPU_TARGETS=gfx1201 -DCMAKE_BUILD_TYPE=Release
HIP_PATH=/opt/rocm cmake --build build -j16 --target llama-server llama-bench
```

Clean build, no errors, no warnings worth noting. Both traps documented in
README.md's rebuild section applied and were avoided the same way (`HIPCXX`
must be `clang`, not `clang++`).

**Flash attention is disabled automatically for this arch:**

```
W resolve_fused_ops: layer 0 is assigned to device ROCm0 but Flash Attention
  is assigned to device CPU (usually due to missing support)
W resolve_fused_ops: Flash Attention not supported, set to disabled
```

So every config below runs without `-fa`, and `-ctk`/`-ctv` KV quantisation was
not attempted — no point testing a flag path this arch already reports as
unsupported.

## VRAM fit — native context only

Only one context was tested: the GGUF's native 32,768. `-ngl 99 -ub 1024 -b
2048`, no flash attention:

| Context | VRAM used (model-attributable) | Peak | Free |
|---|---|---|---|
| 32,768 *(native)* | 13,361 MiB | 14,555 MiB | 1,749 MiB |

Clean fit — `peak >= loaded` and GTT flat at 277 MiB throughout (base 271),
so this is a real allocation, not a host-memory spill (see README.md's `fit.sh`
spill-guard note for what that check catches).

## Throughput

700-token code prompt, temp 0.0, n=3:

| Run | Prompt tok/s | Gen tok/s |
|---|---|---|
| 1 | 394.2 | 100.75 |
| 2 | 89.0 | 100.53 |
| 3 | 88.8 | 101.43 |

Generation is fast and flat (~100 tok/s) — consistent with ~3B active params
on ROCm. Prompt processing collapsed after the first run (394.2 → 89.0), the
same run-to-run instability documented for Gemma 4-E2B in README.md; treat a
single pp reading from a freshly-loaded server on this box with suspicion.

## The reasoning-suppression bug

This is the finding that matters more than any score below. Isolated with a
direct request, `max_tokens: 2400`, `chat_template_kwargs: {enable_thinking:
false}`, server started with `--reasoning-budget 1024`:

```json
{"finish_reason": "length", "message": {"role": "assistant", "content": "..."}}
```

No `reasoning_content` key anywhere in the response — the server never
recognises this as a reasoning model to split. The full 2400-token budget was
consumed by visible `<think>...` prose, and generation stopped mid-sentence,
inside the model's own reasoning, having never reached an answer:

> *"...if new"* (verbatim tail of a 2400-token response to a one-line
> `add_months` prompt — cut off inside a conditional the model was still
> reasoning through)

Every automated probe in this repo's suite uses `enable_thinking:false` plus a
`max_tokens` sized for models where that flag (or `--reasoning-budget`) works —
700 for throughput, 1200 for tool-calling, 2000 for cdn-freshness, 2400 for
code-quality. None of those budgets are reachable here; they all land inside
unbounded chain-of-thought.

## Probe results — read these as "budget exhausted," not "model failed"

**Tool calling: 0/2 probes fired a call.** Single and parallel both returned
prose describing what the model *would* need to do, never a `tool_calls`
array — the 1200-token budget for this probe is well inside typical `<think>`
length for this model on harder prompts.

**Code quality: 0/50 (0.0%).** All seven tasks `DID NOT RUN` —
`extract_code()` found no fenced block (there never was one within budget) and
fell back to the raw truncated reasoning text, which reads as a Python
`SyntaxError` (mostly "unterminated string literal") because it is mid-thought,
not because it is wrong code.

**CDN freshness: 9/51 URLs resolve (18%).** The one simple prompt (prompt 3)
scored 2/2 clean across all three runs — short enough to finish. The two
harder prompts scored 0/10 and 1/5 every run, with several URLs visibly
garbled (`react-dom-server.b umd.js` — a stray space and truncated token,
`react@umd.js` — missing version), consistent with generation being cut off
mid-token by the length limit while still inside reasoning, not with the model
confidently hallucinating a wrong-but-well-formed URL the way other models in
this file do.

## What would need to change

* The fork would need `reasoning_content` splitting wired up for
  `instella-moe`, the way it already exists for `deepseek2` (which this port
  was diffed against) — or the model needs to be served with `max_tokens` large
  enough to survive unbounded thinking, which none of this repo's standard
  probe budgets are.
* Not wired into `switch-model.sh` or `models-preset.ini` — it is not on
  mainline, needs a second toolchain, and cannot currently produce a
  bounded-length answer to a non-trivial prompt.
* Deleted from disk (see top of this file) rather than kept resident, since
  neither the GGUF nor the fork tree is usable as-is. If the fork gets the
  reasoning-format fix upstream, both are a re-download and a re-clone away —
  see Build and The model, above — and worth re-running to finally observe
  the actual coding/tool-calling ability.
