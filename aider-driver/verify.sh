#!/usr/bin/env bash
# test-cmd for aider --auto-test. Exit 0 = clean, nonzero = failures shown to model.
set -uo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

if ! curl -sS -o /dev/null --max-time 2 http://localhost:8000/ 2>/dev/null; then
  nohup python3 -m http.server 8000 >/dev/null 2>&1 &
  disown
  sleep 1.5
fi

python3 "$DIR/verify_browser.py" http://localhost:8000/
exit $?
