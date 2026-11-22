import json

from appcfg.loader import DEFAULTS, load


def test_staging_env_from_crash_log():
    env = {"APP__DB__HOST": "db.staging.internal", "APP__DB__POOL__SIZE": "20",
           "APP__CACHE__REDIS__URL": "redis://cache.staging.internal:6379/0", "APP__HTTP__DEBUG": "false"}
    cfg = load(None, env)
    assert cfg["cache"]["redis"]["url"] == "redis://cache.staging.internal:6379/0"
    assert cfg["db"]["pool"]["size"] == 20 and cfg["http"]["debug"] is False
    assert cfg["db"]["host"] == "db.staging.internal"


def test_new_top_level_key_and_section_in_file(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"feature": {"flags": {"beta": True}}}))
    cfg = load(str(p), {"APP__FEATURE__FLAGS__BETA": "no", "APP__REGION": "ap-southeast-2",
                        "APP__FEATURE__FLAGS__NEWONE": "7"})
    assert cfg["feature"]["flags"]["beta"] is False
    assert cfg["region"] == "ap-southeast-2"
    assert cfg["feature"]["flags"]["newone"] == "7"


def test_defaults_not_mutated():
    before = json.dumps(DEFAULTS, sort_keys=True)
    load(None, {"APP__DB__POOL__SIZE": "99", "APP__CACHE__TTL": "5", "APP__DB__EXTRA__X": "1"})
    load(None, {"APP__HTTP__PORT": "1"})
    assert json.dumps(DEFAULTS, sort_keys=True) == before
    assert load(None, {})["db"]["pool"]["size"] == 5


def test_existing_coercion_kept():
    cfg = load(None, {"APP__DB__PORT": "6543", "APP__HTTP__DEBUG": "on"})
    assert cfg["db"]["port"] == 6543 and cfg["http"]["debug"] is True
