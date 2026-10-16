#!/usr/bin/env python3
"""Strata on the R9700 alone against both cards, same day, same prompts as sweep.py.

Both cards = the production config (pipeline windows 2 + stage trim, split 33).
R9700 alone = the same config on one card: those two settings exist only for a
layer split, so they are removed, not left inert. 200K context for both, so
the single card pays the same KV cost. Order: both, R9700, both again (drift).

    python3 one_vs_two.py
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sweep  # noqa: E402

_base_config = sweep.arm_config


def r9700_config(name, *a, **k):
    p = _base_config(name, *a, **k)
    c = json.loads(p.read_text())
    c["gpu"] = [1]
    c.pop("layer_split", None)
    args = c["args"]
    if "--pipeline-windows" in args:
        i = args.index("--pipeline-windows")
        del args[i:i + 2]
    c.get("env", {}).pop("STRATA_STAGE_TRIM", None)
    p.write_text(json.dumps(c, indent=2))
    return p


if __name__ == "__main__":
    sweep.WORK.mkdir(parents=True, exist_ok=True)
    out = HERE / "one-vs-two.json"
    results = {}
    for name, single in (("both-tuned", False), ("r9700-alone", True), ("both-tuned-again", False)):
        sweep.arm_config = r9700_config if single else _base_config
        results[name] = sweep.run_arm(name, {})
        out.write_text(json.dumps(results, indent=1))
        r = results[name]
        print(name, f"prefill {r['prefill_tok_s']} tok/s  decode {r['decode_tok_s']} tok/s {r['decode_per_prompt']}"
                    f"  hit {r['hit']}  load {r['load_s']}s", flush=True)
