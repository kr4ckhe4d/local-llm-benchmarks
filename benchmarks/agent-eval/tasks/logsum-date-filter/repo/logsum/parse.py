"""Parse Common/Combined Log Format lines."""
import re
from dataclasses import dataclass
from datetime import datetime

LINE = re.compile(r'(?P<host>\S+) \S+ \S+ \[(?P<ts>[^\]]+)\] "(?P<method>\S+) (?P<path>\S+)[^"]*" (?P<status>\d{3}) (?P<size>\S+)')


@dataclass
class Request:
    host: str
    ts: datetime
    method: str
    path: str
    status: int
    size: int


def parse_line(line: str) -> Request | None:
    m = LINE.match(line)
    if not m:
        return None
    return Request(
        host=m["host"],
        ts=datetime.strptime(m["ts"], "%d/%b/%Y:%H:%M:%S %z"),
        method=m["method"],
        path=m["path"].split("?", 1)[0],
        status=int(m["status"]),
        size=0 if m["size"] == "-" else int(m["size"]),
    )


def parse_file(path: str):
    with open(path, errors="replace") as f:
        for line in f:
            r = parse_line(line)
            if r:
                yield r
