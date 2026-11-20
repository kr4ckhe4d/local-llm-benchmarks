#!/usr/bin/env python3
"""Per-layer sizes of a (split) GGUF, and the llama.cpp -ts that fills devices in order to a budget.

    rpc-split.py MODEL-00001-of-0000N.gguf  14.0 30.0 10.0 60.0

Prints `-ts a/b/c/d` (layers per device, in -dev order) and what each device holds.
Layer split puts whole blocks on devices in order; the output head and token
embeddings go with the last device / stay on the host. Budgets are GiB of weights,
so leave room for KV cache and compute buffers yourself.
"""
import glob, re, sys
sys.path.insert(0, f"{__import__('os').path.expanduser('~')}/llama.cpp/gguf-py")
from gguf import GGUFReader

first, budgets = sys.argv[1], [float(x) for x in sys.argv[2:]]
shards = sorted(glob.glob(re.sub(r"-00001-of-(\d{5})\.gguf$", r"-*-of-\1.gguf", first))) or [first]
layers, other = {}, {}
for s in shards:
    for t in GGUFReader(s).tensors:
        m = re.match(r"blk\.(\d+)\.", t.name)
        if m:
            layers[int(m.group(1))] = layers.get(int(m.group(1)), 0) + int(t.n_bytes)
        else:
            other[t.name] = int(t.n_bytes)
G = 2**30
n = len(layers)
print(f"{n} layers, {sum(layers.values())/G:.2f} GiB in blocks, "
      + ", ".join(f"{k} {v/G:.2f}" for k, v in other.items()) + " GiB")
ts, i = [], 0
for d, b in enumerate(budgets):
    used, k = 0, 0
    last = d == len(budgets) - 1
    while i < n and (last or used + layers[i] <= b * G):
        used += layers[i]; i += 1; k += 1
    ts.append(k)
    print(f"  device {d}: {k} layers, {used/G:.2f} GiB (budget {b} GiB)")
if i < n:
    sys.exit(f"does not fit: {n - i} layers left")
print("-ts " + "/".join(map(str, ts)))
