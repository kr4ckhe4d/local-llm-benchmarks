import argparse
import sys
from datetime import date

from .parse import parse_file
from .summary import summarise


def _date(s: str) -> date:
    try:
        return date.fromisoformat(s) if len(s) == 10 else date.fromisoformat("bad")
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid date: {s!r} (expected YYYY-MM-DD)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="logsum", description="Summarise an access log.")
    ap.add_argument("logfile")
    ap.add_argument("--top", type=int, default=5, help="number of paths to list")
    ap.add_argument("--since", type=_date, help="only requests on or after YYYY-MM-DD")
    ap.add_argument("--until", type=_date, help="only requests on or before YYYY-MM-DD")
    a = ap.parse_args(argv)
    reqs = (r for r in parse_file(a.logfile)
            if (a.since is None or r.ts.date() >= a.since) and (a.until is None or r.ts.date() <= a.until))
    print(summarise(reqs, top=a.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
