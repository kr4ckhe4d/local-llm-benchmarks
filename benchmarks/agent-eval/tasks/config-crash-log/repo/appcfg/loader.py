"""Layered config: DEFAULTS <- JSON config file <- APP__ environment overrides."""
import copy
import json
import os

DEFAULTS = {
    "db": {"host": "localhost", "port": 5432, "pool": {"size": 5, "timeout": 2.5}},
    "http": {"port": 8080, "debug": False},
}

PREFIX = "APP__"


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _coerce(raw: str, current):
    if isinstance(current, bool):
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(current, int):
        return int(raw)
    if isinstance(current, float):
        return float(raw)
    return raw


def _set_path(cfg: dict, keys: list[str], raw: str) -> None:
    node = cfg
    for k in keys[:-1]:
        node = node[k]
    leaf = keys[-1]
    node[leaf] = _coerce(raw, node.get(leaf))


def apply_env(cfg: dict, environ) -> dict:
    for name, raw in sorted(environ.items()):
        if not name.startswith(PREFIX):
            continue
        keys = [p.lower() for p in name[len(PREFIX):].split("__") if p]
        if keys:
            _set_path(cfg, keys, raw)
    return cfg


def load(path: str | None = None, environ=None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    if path:
        with open(path) as f:
            cfg = deep_merge(cfg, json.load(f))
    return apply_env(cfg, os.environ if environ is None else environ)
