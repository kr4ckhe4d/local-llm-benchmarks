from collections import Counter


def summarise(requests, top: int = 5) -> str:
    reqs = list(requests)
    status = Counter(r.status // 100 * 100 for r in reqs)
    paths = Counter(r.path for r in reqs)
    lines = [f"requests: {len(reqs)}",
             f"bytes: {sum(r.size for r in reqs)}",
             "status: " + " ".join(f"{k // 100}xx={status[k]}" for k in sorted(status))]
    lines.append("top paths:")
    for p, n in sorted(paths.items(), key=lambda kv: (-kv[1], kv[0]))[:top]:
        lines.append(f"  {n:6d} {p}")
    return "\n".join(lines)
