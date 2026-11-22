import sys

from .importer import import_file


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2 or argv[0] != "import":
        print("usage: ledger import FILE", file=sys.stderr)
        return 2
    txs = import_file(argv[1])
    total = sum(t.amount for t in txs)
    print(f"{len(txs)} transactions, net {total:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
