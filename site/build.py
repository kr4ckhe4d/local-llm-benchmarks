#!/usr/bin/env python3
"""Build the research site into site/dist/.

Only files git would publish are used (tracked + untracked-but-not-ignored), so
anything .gitignore keeps out of the record (handover.md, session logs) stays out
of the site too.

    python3 site/build.py            # -> site/dist/
"""
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
DIST = SITE / "dist"
ASSETS = SITE / "assets"

TEXT_EXT = {".txt", ".log", ".py", ".sh", ".json", ".jsonl", ".md", ".ini", ".c", ".template",
            ".jinja", ".csv", ".tsv", ".diff", ".patch", ".yaml", ".yml", ".toml", ".lock", "",
            ".cpp", ".hpp", ".h", ".hip", ".cu", ".cmake", ".bat", ".html", ".js", ".css"}
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
TOP_LEVEL_EXT = {".sh", ".py", ".ini", ".template", ".jinja"}
MAX_TEXT = 4_000_000


# ---------------------------------------------------------------- projects
HOME = Path.home()


def _order(first):
    return lambda p: (first.index(p) if p in first else len(first), p.lower())


PROJECTS = [
    {   # this repo: tracked + untracked-not-ignored (new benchmark folders count as published)
        "id": "bench", "name": "local-llm-benchmarks", "root": ROOT, "prefix": "",
        "repo": "kr4ckhe4d/local-llm-benchmarks", "branch": "main", "untracked": True,
        "title": "RDNA4 llama.cpp benchmarks",
        "blurb": "Measured local LLMs on RX 9070 XT + Radeon AI PRO R9700 with llama.cpp and ROCm: "
                 "throughput, VRAM fit, KLD vs BF16, MTP, long context, code quality, coding agents.",
        "doc": lambda f: f.endswith(".md") and ("/" not in f or f == "benchmarks/README.md"),
        "raw": lambda f: (f.startswith(("benchmarks/", "aider-driver/", "templates/"))
                          or ("/" not in f and Path(f).suffix in TOP_LEVEL_EXT) or f.endswith(".md")),
        "order": _order(["README.md", "r9700+rx9070.md"]),
    },
    {
        "id": "densemoe", "name": "dense-moe-research", "root": HOME / "code/dense-moe", "prefix": "dense-moe/",
        "repo": "kr4ckhe4d/dense-moe-research", "branch": "master", "untracked": False,
        "title": "Dense to MoE",
        "blurb": "Can a dense LLM be made sparse for faster local inference? Qwen3.5-9B FFNs converted to "
                 "Mixture-of-Experts with Triton kernels on RDNA4, against GGUF quants, MTP and DFlash.",
        "doc": lambda f: f.endswith(".md") and ("/" not in f or re.match(r"docs/[^/]+\.md$", f)),
        "raw": lambda f: not f.startswith(".ai/"),
        "order": _order(["README.md", "docs/conclusions.md", "docs/writeup.md", "docs/findings.md",
                         "docs/research.md", "docs/fast27b.md", "docs/dflash.md", "docs/mtp_tuning.md",
                         "docs/offload.md", "docs/upstream_mmvq.md", "docs/phase3_research.md",
                         "docs/phase3_findings.md", "docs/architecture.md", "docs/environment.md",
                         "docs/roadmap.md", "requirements.md", "gpt-review.md"]),
    },
    {   # a fork of Strata; only oss/ (the gpt-oss engine) is this research, the rest is upstream
        "id": "strataoss", "name": "Strata-oss", "root": HOME / "code/Strata-oss", "prefix": "strata-oss/",
        "repo": "kr4ckhe4d/Strata-oss", "branch": "main", "untracked": False, "subdir": "oss",
        "title": "strata-oss: gpt-oss-120b on a normal PC",
        "blurb": "A gpt-oss (120b/20b) engine on Strata's mechanism: hot experts in VRAM across two cards, "
                 "the rest computed on the CPU from pinned RAM. 91-101 tok/s against llama.cpp's 50.5.",
        "doc": lambda f: f in ("oss/README.md", "oss/FINDINGS.md", "oss/NEXT.md", "oss/PORTING.md",
                               "oss/paper/strata-oss.md"),
        "raw": lambda f: f.startswith("oss/"),
        "order": _order(["oss/README.md", "oss/FINDINGS.md", "oss/paper/strata-oss.md",
                         "oss/PORTING.md", "oss/NEXT.md"]),
    },
    {   # HANDOVER.md is session notes, kept off the site like this repo's handover.md
        "id": "moeinspector", "name": "moe-inspector", "root": HOME / "code/moe-inspector",
        "prefix": "moe-inspector/", "repo": "kr4ckhe4d/moe-inspector", "branch": "main", "untracked": False,
        "title": "MoE Inspector",
        "blurb": "A GUI for looking inside a Mixture-of-Experts model while it generates: per-token expert "
                 "routing heatmaps, expert and layer ablation, and a Strata view of what the VRAM cache keeps.",
        "doc": lambda f: f == "README.md",
        "raw": lambda f: f != "HANDOVER.md",
        "order": _order(["README.md"]),
    },
]


def git(proj, *args):
    return subprocess.run(["git", *args], cwd=proj["root"], capture_output=True, text=True).stdout


def project_files(proj):
    """(published, tracked): files git publishes for this project, and those on GitHub."""
    args = ["ls-files", "-z", "--cached"] + (["--others", "--exclude-standard"] if proj["untracked"] else [])
    if proj.get("subdir"):
        args += ["--", proj["subdir"]]
    files = sorted({p for p in git(proj, *args).split("\0") if p and (proj["root"] / p).is_file()})
    files = [p for p in files if not p.startswith("site/") and "__pycache__" not in p]
    tracked = set(p for p in git(proj, "ls-files", "-z", "--cached").split("\0") if p)
    return files, tracked


# ---------------------------------------------------------------- markdown
def slugify_heading(text):
    s = text.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def doc_slug(path):
    """path is the site path (project prefix included)."""
    if path == "README.md":
        return "readme"
    return re.sub(r"[^a-z0-9]+", "-", path[:-3].lower()).strip("-")


def inline_text(tok):
    if tok.children is None:
        return tok.content
    return "".join(c.content for c in tok.children if c.type in ("text", "code_inline"))


def render_doc(proj, rel, doc_slugs, fileset, dirset, tracked):
    path = proj["prefix"] + rel
    src = (proj["root"] / rel).read_text(encoding="utf-8", errors="replace")
    gh = f"https://github.com/{proj['repo']}"
    md = MarkdownIt("commonmark", {"html": True, "linkify": False, "typographer": False})
    md.enable(["table", "strikethrough"])
    tokens = md.parse(src)
    base = str(Path(rel).parent)
    base = "" if base == "." else base
    slug = doc_slug(path)
    links = set()

    def rewrite(href):
        if not href or re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I):
            return href, True
        if href.startswith("#"):
            return f"#/doc/{slug}/{href[1:]}", False
        target, _, anchor = href.partition("#")
        norm = str(Path(base, target)) if base else target
        norm = re.sub(r"/+$", "", str(Path(norm)))
        while "/../" in "/" + norm:
            norm = re.sub(r"(^|/)[^/]+/\.\.(/|$)", r"\1", norm, count=1)
        if norm.startswith("../"):
            return href, True
        sp = proj["prefix"] + norm
        if sp in doc_slugs:
            return f"#/doc/{doc_slugs[sp]}" + (f"/{anchor}" if anchor else ""), False
        if proj["id"] == "bench" and norm.startswith("benchmarks/"):
            links.add(norm.split("/")[1])
        if sp in fileset:
            return f"#/files/{sp}", False
        if sp in dirset:
            return f"#/files/{sp}/", False
        if norm in tracked:   # in the repo but not mirrored here: send it to GitHub
            return f"{gh}/blob/{proj['branch']}/{norm}" + (f"#{anchor}" if anchor else ""), True
        if any(t.startswith(norm + "/") for t in tracked):
            return f"{gh}/tree/{proj['branch']}/{norm}", True
        return href, True

    toc, sections, used = [], [], {}
    cur = {"id": "", "title": Path(path).stem, "level": 1, "text": []}
    title = None
    for i, t in enumerate(tokens):
        if t.type == "heading_open":
            text = inline_text(tokens[i + 1])
            hid = slugify_heading(text) or "section"
            n = used.get(hid, 0)
            used[hid] = n + 1
            if n:
                hid = f"{hid}-{n}"
            t.attrSet("id", hid)
            level = int(t.tag[1])
            if level == 1 and title is None:
                title = text
            if level in (2, 3, 4):
                toc.append({"id": hid, "title": text, "level": level})
            sections.append(cur)
            cur = {"id": hid, "title": text, "level": level, "text": []}
        elif t.type == "inline":
            if not (i > 0 and tokens[i - 1].type == "heading_open"):
                cur["text"].append(inline_text(t))
            for c in t.children or []:
                if c.type == "link_open":
                    new, ext = rewrite(c.attrGet("href"))
                    c.attrSet("href", new)
                    if ext:
                        c.attrSet("target", "_blank")
                        c.attrSet("rel", "noopener")
                elif c.type == "image":
                    srcp = c.attrGet("src")
                    if srcp and not re.match(r"^[a-z]+:", srcp):
                        norm = str(Path(base, srcp)) if base else srcp
                        if proj["prefix"] + norm in fileset:
                            c.attrSet("src", f"raw/{proj['prefix']}{norm}")
                        else:
                            c.attrSet("src", f"https://raw.githubusercontent.com/{proj['repo']}/{proj['branch']}/{norm}")
        elif t.type in ("fence", "code_block"):
            cur["text"].append(t.content[:1500])
    sections.append(cur)

    html = md.renderer.render(tokens, md.options, {})
    # wrap tables so they scroll on narrow screens
    html = html.replace("<table>", '<div class="tbl"><table>').replace("</table>", "</table></div>")
    words = len(re.findall(r"\w+", src))
    secs = []
    for s in sections:
        txt = re.sub(r"\s+", " ", " ".join(s["text"])).strip()
        if txt or s["id"]:
            secs.append({"id": s["id"], "title": s["title"], "level": s["level"], "text": txt[:8000]})
    return {
        "slug": slug, "path": path, "title": title or path, "html": html, "toc": toc,
        "words": words, "sections": secs, "links": sorted(links), "project": proj["id"],
        "gh": f"{gh}/blob/{proj['branch']}/{rel}" if rel in tracked else None,
    }


# ---------------------------------------------------------------- probe parsers
HDR = re.compile(r"^#\s*([a-z][a-z ]*?)\s*:\s*(.*)$")


def header(text):
    h = {}
    for line in text.splitlines()[:14]:
        m = HDR.match(line)
        if m and m.group(1) not in h:
            h[m.group(1).strip()] = m.group(2).strip()
    return h


def build_of(h):
    m = re.search(r"build (\d+)", h.get("host", "") + " " + h.get("build", ""))
    return int(m.group(1)) if m else None


def parse_code_quality(text):
    m = re.search(r"^(\S+): (\d+)/(\d+) checks pass \(([\d.]+)%\) \| (\d+)/(\d+) tasks fully clean",
                  text, re.M)
    if not m:
        return None
    tasks = []
    for tm in re.finditer(r"^\s{2}(\w+)\s+(\d+)/(\d+)\s+(clean|missed: ([^\[\n]*?))(?:\s+\[(.*)\])?\s*$", text, re.M):
        tasks.append({"task": tm.group(1), "pass": int(tm.group(2)), "total": int(tm.group(3)),
                      "missed": [x.strip() for x in (tm.group(5) or "").split(",") if x.strip()],
                      "note": tm.group(6)})
    # keep the last block of per-task rows (files may hold several attempts)
    seen, uniq = set(), []
    for t in reversed(tasks):
        if t["task"] not in seen:
            seen.add(t["task"])
            uniq.append(t)
    return {"label": m.group(1), "pass": int(m.group(2)), "total": int(m.group(3)),
            "clean": int(m.group(5)), "ntasks": int(m.group(6)), "tasks": list(reversed(uniq))}


def mean(xs):
    return sum(xs) / len(xs) if xs else None


def parse_throughput(text):
    tg = [float(x) for x in re.findall(r"tg\s+([\d.]+) tok/s", text)]
    pp = [float(x) for x in re.findall(r"\bpp\s+([\d.]+) tok/s", text)]
    pp += [float(x) for x in re.findall(r"prompt\s+\d+ tok @\s+([\d.]+) tok/s", text)]
    draft = re.findall(r"draft (\d+)/(\d+)", text)
    vram = re.search(r"VRAM (\d+) MiB", text)
    note = re.search(r"^# NOTE: (.*)$", text, re.M)
    if not tg:
        return None
    return {"note": note.group(1).strip() if note else None, "tg": round(mean(tg), 2), "tg_runs": tg,
            "pp": round(mean(pp[1:] if len(pp) > 1 else pp), 1) if pp else None,
            "draft": round(100 * sum(int(a) for a, _ in draft) / sum(int(b) for _, b in draft), 1) if draft else None,
            "vram": int(vram.group(1)) if vram else None}


def parse_kld(text):
    def g(pat):
        m = re.search(pat, text, re.M)
        return float(m.group(1)) if m else None
    k = g(r"^Mean\s+KLD:\s+(-?[\d.]+)")
    if k is None:
        return None
    return {"kld": k, "kld99": g(r"^99\.0%\s+KLD:\s+([\d.]+)"), "median": g(r"^Median\s+KLD:\s+([\d.]+)"),
            "same_top": g(r"^Same top p:\s+([\d.]+)"), "rms_dp": g(r"^RMS Δp\s+:\s+([\d.]+)"),
            "ppl_ratio": g(r"^Mean PPL\(Q\)/PPL\(base\)\s+:\s+([\d.]+)"), "ppl": g(r"^Mean PPL\(Q\)\s+:\s+([\d.]+)")}


def parse_cdn(text):
    m = re.search(r": (\d+)/(\d+) URLs resolve \((\d+)%\) \| (\d+)/(\d+) runs fully clean", text)
    if not m:
        return None
    return {"ok": int(m.group(1)), "total": int(m.group(2)), "pct": int(m.group(3)),
            "clean": int(m.group(4)), "runs": int(m.group(5))}


def parse_tools(text):
    s = re.search(r"^SINGLE\s*: calls=(\d+)", text, re.M)
    p = re.search(r"^PARALLEL\s*: calls=(\d+)", text, re.M)
    if not s and not p:
        return None
    ok = "1355528" in text and "PROBE-770487" in text
    return {"single": int(s.group(1)) if s else None, "parallel": int(p.group(1)) if p else None, "ok": ok}


def parse_fit(text):
    fits = [int(x) for x in re.findall(r"^ctx=(\d+)\s+model=", text, re.M)]
    return {"max_ctx": max(fits) if fits else None, "rows": len(fits)}


STRATA_ARMS = {
    "base": "defaults", "base-again": "defaults (repeat)", "adapt-async": "--adapt-async 1",
    "pipeline-w2": "--pipeline-windows 2", "split-own": "STRATA_SPLIT_OWN=1",
    "stage-trim": "STRATA_STAGE_TRIM=1, split 33", "spec3": "--spec 3", "spec5": "--spec 5",
    "spec6": "--spec 6", "pw2+trim": "pipeline-windows 2 + stage trim",
    "pw2+trim+spec5": "pw2 + trim + --spec 5", "both-tuned": "both cards, tuned",
    "r9700-alone": "R9700 alone", "both-tuned-again": "both cards, tuned (repeat)",
}


def parse_strata(fileset):
    """Strata writes JSON, not the llama.cpp probe text files."""
    out = {"tuning": [], "cards": [], "modes": [], "adapt": []}
    for name, key in (("benchmarks/strata-tuning/results.json", "tuning"),
                      ("benchmarks/strata-tuning/one-vs-two.json", "cards")):
        if name not in fileset:
            continue
        for arm, r in json.loads((ROOT / name).read_text()).items():
            d = r.get("decode_per_prompt") or []
            out[key].append({"arm": arm, "label": STRATA_ARMS.get(arm, arm), "path": name,
                             "prefill": r.get("prefill_tok_s"), "decode": r.get("decode_tok_s"),
                             "code": d[:3], "prose": d[3:6], "load_s": r.get("load_s"),
                             "hit": round(sum(r["hit"]) / len(r["hit"]), 2) if r.get("hit") else None})
    name = "benchmarks/strata-expert-modes/results.json"
    if name in fileset:
        for prof, doms in json.loads((ROOT / name).read_text()).items():
            for dom, runs in doms.items():
                g = sum(x["gen_tokens"] for x in runs)
                out["modes"].append({"profile": prof, "domain": dom, "path": name,
                                     "tok_s": round(g / sum(x["gen_ms"] for x in runs) * 1000, 1),
                                     "hit": round(100 * sum(x["hits"] for x in runs) / sum(x["lookups"] for x in runs), 1),
                                     "ssd_mb": round(sum(x["ssd_mb"] for x in runs) / len(runs), 1)})
    name = "benchmarks/strata-expert-modes/results-adapt.json"
    if name in fileset:
        for seq, runs in json.loads((ROOT / name).read_text()).items():
            out["adapt"].append({"seq": seq, "path": name, "runs": [
                {"i": i + 1, "domain": x.get("domain"), "tok_s": x["tok_s"],
                 "hit": round(100 * x["hits"] / x["lookups"], 1)} for i, x in enumerate(runs)]})
    return out


# ---------------------------------------------------------------- main
def main():
    # site path -> (project, repo-relative path); other projects live under their prefix
    entries, proj_docs, tracked_by = {}, {}, {}
    for proj in PROJECTS:
        if not (proj["root"] / ".git").exists():
            print(f"skip {proj['name']}: {proj['root']} not found", file=sys.stderr)
            continue
        files, tracked = project_files(proj)
        tracked_by[proj["id"]] = tracked
        for f in files:
            if proj["raw"](f) or proj["doc"](f):
                entries[proj["prefix"] + f] = (proj, f)
        proj_docs[proj["id"]] = sorted((f for f in files if proj["doc"](f)), key=proj["order"])
    fileset = set(entries)
    files = sorted(entries)
    dirset = set()
    for f in files:
        p = Path(f).parent
        while str(p) != ".":
            dirset.add(str(p))
            p = p.parent

    doc_slugs = {}
    for proj in PROJECTS:
        for rel in proj_docs.get(proj["id"], []):
            doc_slugs[proj["prefix"] + rel] = doc_slug(proj["prefix"] + rel)
    docs = [render_doc(proj, rel, doc_slugs, fileset, dirset, tracked_by[proj["id"]])
            for proj in PROJECTS for rel in proj_docs.get(proj["id"], [])]

    # files published as raw
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "raw").mkdir(parents=True)
    tree = []
    for f in files:
        proj, rel = entries[f]
        src = proj["root"] / rel
        ext = src.suffix.lower()
        size = src.stat().st_size
        if ext not in TEXT_EXT and ext not in IMG_EXT:
            continue
        if ext in TEXT_EXT and size > MAX_TEXT:
            continue
        dst = DIST / "raw" / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        entry = {"p": f, "s": size, "m": int(src.stat().st_mtime)}
        if rel in tracked_by[proj["id"]]:
            entry["g"] = 1
        if ext in (".txt", ".log") and proj["id"] == "bench":
            h = header(src.read_text(errors="replace")[:3000])
            if h:
                entry["h"] = h
        tree.append(entry)

    # probes, keyed by folder
    measurements = {"code": [], "throughput": [], "kld": [], "cdn": [], "tools": [], "fit": []}
    for e in tree:
        f = e["p"]
        if not f.startswith("benchmarks/") or not f.endswith(".txt"):
            continue
        rel = f[len("benchmarks/"):]
        parts = rel.split("/")
        text = (ROOT / f).read_text(errors="replace")
        h = e.get("h", {})
        folder = parts[0]
        if folder == "q8ref" and len(parts) > 2:
            model = parts[1]
        elif folder == "raw":
            model = "/".join(parts[:-1])
        else:
            model = folder
        common = {"path": f, "folder": folder, "model": model, "file": parts[-1],
                  "date": h.get("date", "")[:19], "flags": h.get("flags"), "ctx": h.get("ctx"),
                  "build": build_of(h), "gguf": h.get("model")}
        if len(parts) == 1:
            continue  # top-level probe outputs (claude-compat.txt etc.) aren't per-model
        cq = parse_code_quality(text) if "checks pass" in text else None
        if cq:
            measurements["code"].append({**common, **cq})
        name = parts[-1]
        if name.startswith("throughput"):
            r = parse_throughput(text)
            if r:
                measurements["throughput"].append({**common, **r})
        if name == "kld.txt" or (name.startswith("kld") and "Mean    KLD" in text and folder != "raw"):
            r = parse_kld(text)
            if r:
                ref = "q8_0" if folder == "q8ref" else ("bf16" if "bf16" in h.get("base", "").lower() else h.get("base", "?"))
                measurements["kld"].append({**common, **r, "ref": ref, "base": h.get("base")})
        if name.startswith("cdn-freshness"):
            r = parse_cdn(text)
            if r:
                measurements["cdn"].append({**common, **r})
        if name.startswith("tool-calling"):
            r = parse_tools(text)
            if r:
                measurements["tools"].append({**common, **r})
        if name == "fit.txt":
            r = parse_fit(text)
            if r["max_ctx"]:
                measurements["fit"].append({**common, **r})

    strata = parse_strata(fileset)  # bench paths are unprefixed
    prod = next((a for a in strata["tuning"] if a["arm"] == "pw2+trim"), None)
    if prod:
        measurements["throughput"].append({
            "path": prod["path"], "folder": "qwen3.8-flash-next-IQ3_XXS-strata",
            "model": "qwen3.8-flash-next-IQ3_XXS-strata", "file": "results.json", "date": "2026-10-12",
            "flags": "Strata 0.1.43, --pipeline-windows 2, STRATA_STAGE_TRIM=1, layer_split 33, 200K, int8 KV",
            "ctx": "204800", "build": None, "gguf": "Qwen3.8-Flash-Next IQ3_XXS", "engine": "strata",
            "tg": prod["decode"], "tg_runs": prod["code"] + prod["prose"], "pp": prod["prefill"],
            "draft": None, "vram": None,
            "probe": "Strata sweep: 6 prompts (3 code, 3 prose), 1,000 tokens, temp 0; prefill on a cold 29K prompt"})
    measurements["strata"] = strata

    projects = []
    for proj in PROJECTS:
        if proj["id"] not in tracked_by:
            continue
        sub = ["--", proj["subdir"]] if proj.get("subdir") else []
        h, date, msg = (git(proj, "log", "-1", "--format=%h|%cI|%s", *sub).strip().split("|", 2) + ["", "", ""])[:3]
        projects.append({
            "id": proj["id"], "name": proj["name"], "title": proj["title"], "blurb": proj["blurb"],
            "prefix": proj["prefix"], "subdir": proj.get("subdir"), "branch": proj["branch"],
            "url": f"https://github.com/{proj['repo']}", "repo": proj["repo"],
            "commit": h, "commit_date": date, "commit_msg": msg,
            "commits": int(git(proj, "rev-list", "--count", "HEAD", *sub).strip() or 0),
            "docs": len(proj_docs[proj["id"]]),
            "files": sum(1 for e in tree if entries[e["p"]][0] is proj),
        })
    meta = {"built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "commit": projects[0]["commit"], "commits": projects[0]["commits"], "projects": projects}

    docs_meta = [{k: d[k] for k in ("slug", "path", "title", "toc", "words", "links", "project", "gh")} for d in docs]
    (DIST / "docs").mkdir()
    for d in docs:
        (DIST / "docs" / f"{d['slug']}.html").write_text(d["html"], encoding="utf-8")
    search = [{"d": d["slug"], "i": s["id"], "t": s["title"], "x": s["text"]}
              for d in docs for s in d["sections"]]

    data = {"meta": meta, "docs": docs_meta, "files": tree, "m": measurements}
    (DIST / "data.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    (DIST / "search.json").write_text(json.dumps(search, separators=(",", ":"), ensure_ascii=False),
                                      encoding="utf-8")
    for a in ASSETS.iterdir():
        shutil.copy2(a, DIST / a.name)
    total = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    print(f"docs={len(docs)} files={len(tree)} code={len(measurements['code'])} "
          f"tput={len(measurements['throughput'])} kld={len(measurements['kld'])} "
          f"cdn={len(measurements['cdn'])} tools={len(measurements['tools'])} fit={len(measurements['fit'])} "
          f"size={total/1e6:.1f}MB", file=sys.stderr)


if __name__ == "__main__":
    main()
