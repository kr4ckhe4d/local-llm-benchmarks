import pathlib
import subprocess
import sys

SAMPLE = pathlib.Path(__file__).with_name("sample.log")


def run(*args):
    return subprocess.run([sys.executable, "-m", "logsum", *args], capture_output=True, text=True)


def test_full_summary():
    p = run(str(SAMPLE))
    assert p.returncode == 0
    assert p.stdout.splitlines()[:3] == ["requests: 6", "bytes: 2112", "status: 2xx=4 4xx=1 5xx=1"]


def test_top_paths():
    out = run(str(SAMPLE), "--top", "2").stdout.splitlines()
    assert out[3] == "top paths:"
    assert out[4].split() == ["3", "/api/items"] and out[5].split() == ["2", "/index.html"]
    assert len(out) == 6
