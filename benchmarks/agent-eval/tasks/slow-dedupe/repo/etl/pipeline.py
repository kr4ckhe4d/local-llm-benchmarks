import json

from .dedupe import dedupe


def run(lines):
    records = [json.loads(l) for l in lines if l.strip()]
    return dedupe(records, key=lambda r: (r.get("source"), r.get("id")))
