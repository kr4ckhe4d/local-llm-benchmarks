import json

from appcfg.loader import DEFAULTS, load


def test_defaults():
    assert load(None, {})["db"]["port"] == 5432


def test_file_merge(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"db": {"host": "h"}}))
    cfg = load(str(p), {})
    assert cfg["db"]["host"] == "h" and cfg["db"]["port"] == 5432


def test_env_coercion():
    cfg = load(None, {"APP__DB__PORT": "6543", "APP__HTTP__DEBUG": "true", "APP__DB__POOL__TIMEOUT": "1.5"})
    assert cfg["db"]["port"] == 6543
    assert cfg["http"]["debug"] is True
    assert cfg["db"]["pool"]["timeout"] == 1.5


def test_other_env_ignored():
    assert load(None, {"HOME": "/x"})["http"]["port"] == 8080
