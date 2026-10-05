#!/usr/bin/env python3
"""Quantisation drift measured through llama-server, on chat-formatted prompts.

Added 2026-10-06 because kld-test.sh (llama-perplexity on raw wikitext) gives
an unusable reference on Gemma 4: Q8_0 at PPL ~20,000, and the score pass reads
that same base file back as 7,439 (r9700+rx9070.md, "Open"). This measures the
same thing a different way, through the path the models are actually served on:

  1. The REFERENCE model (Q8_0) answers each prompt greedily, thinking off.
     Its answer tokens are the fixed text both models are then scored on.
  2. Each model is teacher-forced along that text one token at a time: the
     prompt plus the first i answer tokens go in, one token comes out with its
     top-K log-probabilities (temperature -1: raw softmax, no samplers).
     cache_prompt means each step decodes only the one new token.
     A position whose next token is part of a multi-byte character comes back
     without probabilities (a llama-server rule); it is skipped and counted.
  3. Per position: top-1 agreement, and KL(ref || test) over the reference's
     top-K. Tokens missing from the test model's top-K get its K-th logprob,
     the most they could have, so the KLD is a lower bound on what the test
     model is missing. The mass outside the reference's top-K is ignored.

So the KLD here is an approximation and is NOT the number kld-test.sh prints.
Calibrate before reading it: run a pair kld-test.sh has measured (Qwen3.8
IQ4_XS vs Q8_0, mean KLD 0.0182, top-1 94.07%) and compare.

  python3 chat-kld.py run  <label> <model.gguf> <out.json> [--ref ref.json]
  python3 chat-kld.py cmp  <ref.json> <test.json>

`run` without --ref makes a reference (generates the answers, then forces).
`run --ref` forces the test model along the reference's answer tokens.
Nothing else may hold the GPUs; fit.sh's rule applies.
"""
import json, math, os, subprocess, sys, time, urllib.request

BIN = "/home/nipuna/llama.cpp/build/bin/llama-server"
MODELS = "/home/nipuna/llama.cpp/models"
PORT = 8099
K = 100
N_ANSWER = int(os.environ.get("N_ANSWER", 160))
FLAGS = ["-ngl", "99", "-np", "1", "-c", "8192", "-fa", "on", "--load-mode", "dio"]

PROMPTS = [
    # code
    "Write a Python function that merges overlapping intervals, with a docstring.",
    "Explain what this does and find the bug: `for i in range(len(xs)): if xs[i] == x: xs.remove(x)`",
    "Write a bash one-liner that finds the ten largest files under the current directory.",
    "Show a minimal Rust example of sharing a counter between threads with Arc and Mutex.",
    "Write a SQL query returning each customer's most recent order from orders(customer_id, id, created_at).",
    "What is the difference between a process and a thread? Answer for a junior engineer.",
    "Convert this to TypeScript with types: function add(a, b) { return a + b }",
    "Write a regular expression that matches ISO 8601 dates like 2026-10-06 and explain each part.",
    # knowledge
    "Why is the sky blue? Explain Rayleigh scattering briefly.",
    "Summarise the causes of the First World War in one paragraph.",
    "What does the mitochondrion do in a cell?",
    "Explain how public-key cryptography lets two strangers agree on a secret.",
    "What is the difference between weather and climate?",
    "Who was Ada Lovelace and why is she remembered?",
    "Explain inflation to a twelve-year-old.",
    "How does a transformer language model predict the next token?",
    # reasoning and maths
    "A bat and a ball cost $1.10 in total. The bat costs $1.00 more than the ball. How much is the ball? Show your working.",
    "If it takes 5 machines 5 minutes to make 5 widgets, how long do 100 machines take to make 100 widgets?",
    "Solve for x: 3x + 7 = 2x - 5. Show each step.",
    "Is 221 prime? Explain how you checked.",
    "Three friends split a $96 bill; one pays twice as much as each of the others. How much does each pay?",
    "What is the derivative of x^3 * sin(x)? Show the product rule.",
    "Estimate how many piano tuners work in Chicago, stating your assumptions.",
    "A train leaves at 14:40 and arrives at 17:15. How long is the journey?",
    # writing and instruction following
    "Write a haiku about a server room at night.",
    "Draft a polite two-sentence email declining a meeting invitation.",
    "Give me five names for a coffee shop run by retired astronauts.",
    "Rewrite this sentence to be more concise: 'At this point in time we are not in a position to make a decision.'",
    "List three pros and three cons of working from home, as bullet points.",
    "Write the opening paragraph of a mystery story set on a night train.",
    "Translate into French: 'The library closes early on Sundays.'",
    "Explain the rules of chess castling in plain English.",
]


def post(path, body, timeout=600):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=timeout))


def start(model):
    log = open(f"/tmp/claude-1000/chat-kld-{os.path.basename(model)}.log", "w")
    p = subprocess.Popen([BIN, "-m", f"{MODELS}/{model}", *FLAGS, "--host", "127.0.0.1", "--port", str(PORT)],
                         stdout=log, stderr=subprocess.STDOUT)
    for _ in range(600):
        if p.poll() is not None:
            sys.exit(f"llama-server exited rc={p.returncode}")
        try:
            if b"ok" in urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=2).read():
                return p
        except Exception:
            pass
        time.sleep(1)
    p.kill(); sys.exit("llama-server never became healthy")


def prompt_tokens(text):
    tpl = post("/apply-template", {"messages": [{"role": "user", "content": text}],
                                   "chat_template_kwargs": {"enable_thinking": False}})["prompt"]
    return post("/tokenize", {"content": tpl, "add_special": True, "parse_special": True})["tokens"]


def force(ptoks, answer):
    """Top-K logprobs at each answer position, teacher-forced."""
    out = []
    for i in range(len(answer)):
        r = post("/completion", {"prompt": ptoks + answer[:i], "n_predict": 1, "temperature": -1,
                                 "n_probs": K, "cache_prompt": True, "return_tokens": True})
        # llama-server withholds probabilities when the next token is part of
        # a multi-byte character (first byte of an emoji, say). Rare; such
        # positions are recorded as None and skipped by cmp, which counts them.
        cp = r.get("completion_probabilities")
        out.append({str(t["id"]): t["logprob"] for t in cp[0]["top_logprobs"]} if cp else None)
    return out


def run(label, model, out, ref=None):
    srv = start(model)
    try:
        items = []
        refd = json.load(open(ref)) if ref else None
        for n, text in enumerate(PROMPTS):
            ptoks = prompt_tokens(text)
            if refd:
                assert refd["items"][n]["prompt_tokens"] == ptoks, f"prompt {n} tokenises differently"
                answer = refd["items"][n]["answer"]
            else:
                r = post("/completion", {"prompt": ptoks, "n_predict": N_ANSWER, "temperature": 0.0,
                                         "cache_prompt": False, "return_tokens": True})
                answer = r["tokens"]
            t0 = time.time()
            items.append({"prompt": text, "prompt_tokens": ptoks, "answer": answer, "top": force(ptoks, answer)})
            print(f"  [{n+1:2}/{len(PROMPTS)}] {len(answer):3} tok forced in {time.time()-t0:5.1f}s", flush=True)
        json.dump({"label": label, "model": model, "k": K, "items": items}, open(out, "w"))
    finally:
        srv.terminate(); srv.wait(30)


def cmp(ref, test):
    R, T = json.load(open(ref)), json.load(open(test))
    klds, agree, n, skipped = [], 0, 0, 0
    for ri, ti in zip(R["items"], T["items"]):
        assert ri["answer"] == ti["answer"]
        for rp, tp in zip(ri["top"], ti["top"]):
            if rp is None or tp is None:
                skipped += 1
                continue
            floor = min(tp.values())
            kl = sum(math.exp(lr) * (lr - tp.get(tok, floor)) for tok, lr in rp.items())
            klds.append(max(kl, 0.0))
            agree += max(rp, key=rp.get) == max(tp, key=tp.get)
            n += 1
    klds.sort()
    mean = sum(klds) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in klds) / (n - 1))
    print(f"{T['label']} vs {R['label']}: {n} positions over {len(R['items'])} prompts"
          f" ({skipped} skipped: probabilities withheld mid-character)")
    print(f"  mean KLD (top-{R['k']} approx) : {mean:.6f} +/- {sd/math.sqrt(n):.6f}")
    print(f"  median KLD                 : {klds[n//2]:.6f}")
    print(f"  99% KLD                    : {klds[int(n*0.99)]:.6f}")
    print(f"  same top-1                 : {100*agree/n:.3f}% +/- {100*math.sqrt(agree/n*(1-agree/n)/n):.3f}%")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "run" and len(a) in (4, 6):
        run(a[1], a[2], a[3], a[5] if len(a) == 6 and a[4] == "--ref" else None)
    elif a and a[0] == "cmp" and len(a) == 3:
        cmp(a[1], a[2])
    else:
        sys.exit(__doc__)
