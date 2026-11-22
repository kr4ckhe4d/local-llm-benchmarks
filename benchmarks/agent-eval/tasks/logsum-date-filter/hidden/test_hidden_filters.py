import pathlib
import subprocess
import sys

SAMPLE = pathlib.Path("tests/sample.log").resolve()


def run(*args):
    return subprocess.run([sys.executable, "-m", "logsum", *args], capture_output=True, text=True)


def head(*args):
    p = run(*args)
    assert p.returncode == 0, p.stderr
    return p.stdout.splitlines()[:3]


def test_since():
    assert head(str(SAMPLE), "--since", "2026-11-21") == ["requests: 4", "bytes: 576", "status: 2xx=2 4xx=1 5xx=1"]


def test_until_includes_whole_day():
    assert head(str(SAMPLE), "--until", "2026-11-20") == ["requests: 2", "bytes: 1536", "status: 2xx=2"]


def test_both_uses_written_local_date():
    # the -0500 entry is 22 Nov in UTC but 21 Nov as written; it must count for the 21st
    assert head("--since", "2026-11-21", "--until", "2026-11-21", str(SAMPLE)) == \
        ["requests: 3", "bytes: 576", "status: 2xx=2 4xx=1"]


def test_empty_range():
    assert head(str(SAMPLE), "--since", "2026-12-01")[0] == "requests: 0"


def test_invalid_date():
    for bad in ("21-11-2026", "2026-13-01", "yesterday"):
        p = run(str(SAMPLE), "--since", bad)
        assert p.returncode == 2 and "invalid date" in p.stderr
    p = run(str(SAMPLE), "--until", "2026-02-30")
    assert p.returncode == 2 and "invalid date" in p.stderr


def test_unchanged_without_flags():
    p = run(str(SAMPLE), "--top", "2")
    assert p.stdout.splitlines() == ["requests: 6", "bytes: 2112", "status: 2xx=4 4xx=1 5xx=1", "top paths:",
                                     "       3 /api/items", "       2 /index.html"]
