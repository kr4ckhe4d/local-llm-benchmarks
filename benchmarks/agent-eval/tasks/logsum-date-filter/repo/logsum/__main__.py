import argparse
import sys

from .parse import parse_file
from .summary import summarise


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="logsum", description="Summarise an access log.")
    ap.add_argument("logfile")
    ap.add_argument("--top", type=int, default=5, help="number of paths to list")
    a = ap.parse_args(argv)
    print(summarise(parse_file(a.logfile), top=a.top))
    return 0


if __name__ == "__main__":
    sys.exit(main())
