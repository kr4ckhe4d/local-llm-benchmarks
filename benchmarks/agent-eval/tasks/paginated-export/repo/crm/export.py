import csv
import io

from .client import ContactClient

FIELDS = ("id", "name", "email")


def export_csv(client: ContactClient) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, extrasaction="ignore")
    w.writeheader()
    for c in client.fetch_all():
        w.writerow(c)
    return buf.getvalue()
