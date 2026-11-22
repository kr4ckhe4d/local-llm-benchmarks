import sys

from .loader import load


def main():
    cfg = load(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"starting on :{cfg['http']['port']} db={cfg['db']['host']}:{cfg['db']['port']}")


if __name__ == "__main__":
    main()
