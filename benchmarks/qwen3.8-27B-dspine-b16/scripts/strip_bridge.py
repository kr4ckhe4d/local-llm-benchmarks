import sys, json, shutil, pathlib
from safetensors import safe_open
from safetensors.torch import save_file
src, dst = map(pathlib.Path, sys.argv[1:3])
dst.mkdir(parents=True, exist_ok=True)
keep, drop = {}, []
with safe_open(src/"model.safetensors", "pt") as f:
    for k in f.keys():
        t = f.get_tensor(k)
        if k.startswith("selected_prefix_bridge") or t.dim() == 0:
            drop.append((k, tuple(t.shape), t.numel())); continue
        keep[k] = t
save_file(keep, str(dst/"model.safetensors"), metadata={"format": "pt"})
cfg = json.load(open(src/"config.json"))
for k in ("selected_prefix_code_bridge",): cfg["dflash_config"].pop(k, None)
json.dump(cfg, open(dst/"config.json", "w"), indent=2)
print("kept", len(keep), "params", sum(t.numel() for t in keep.values()))
print("dropped", len(drop), "params", sum(n for *_, n in drop))
for d in drop: print("  ", d[0], d[1])
