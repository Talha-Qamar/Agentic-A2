"""Standalone portfolio loader + search used when the server runs outside GigBid (e.g. `uvx` in Claude
Desktop). Layout of a portfolio folder (every part optional):

    cv.pdf | cv.md                 case_studies/*.md (optional YAML front matter: project, date, client_industry, repo)
    repos/<name>/README.md + code  reviews.json  [{client, rating, text, date, project}]
    past_proposals.jsonl           {proposal_id, date, job_title, text, outcome: won|replied|ignored, cited_projects}

Search is BM25 (always available) fused with dense embeddings when `fastembed` is installed.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

TOKEN = re.compile(r"[a-z0-9][a-z0-9.+#/-]*[a-z0-9+#]|[a-z0-9]")


@dataclass
class Item:
    id: str
    type: str
    source: str
    title: str
    text: str
    date: str | None = None
    outcome: str | None = None
    project: str | None = None
    client_industry: str | None = None
    meta: dict = field(default_factory=dict)


def _fm(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    meta = dict(line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)
    return {k.strip(): v.strip() for k, v in meta.items()}, text[m.end():]


def load_portfolio(base: Path) -> list[Item]:
    base = Path(base).expanduser()
    items: list[Item] = []
    for p in sorted((base / "case_studies").glob("*.md")):
        meta, body = _fm(p.read_text(errors="ignore"))
        body = re.sub(r"<!--.*?-->", "", body, flags=re.S).strip()
        title = (re.search(r"^#\s+(.+)$", body, re.M) or re.search(r"(.+)", body)).group(1)
        items.append(Item(meta.get("project") or p.stem, "case_study", f"case_studies/{p.name}", title, body,
                          meta.get("date"), None, meta.get("project") or p.stem, meta.get("client_industry"), meta))
    if (base / "repos").exists():
        for r in sorted(x for x in (base / "repos").iterdir() if x.is_dir()):
            for f in sorted(r.rglob("*")):
                if f.is_file() and f.suffix in (".md", ".py", ".ts", ".tsx", ".js", ".sql", ".txt", ".json", ".toml", ".yml"):
                    kind = "readme" if f.name.lower() == "readme.md" else "code"
                    items.append(Item(f"repo:{r.name}/{f.relative_to(r)}", kind, f"repos/{r.name}/{f.relative_to(r)}",
                                      f"{r.name}/{f.relative_to(r)}", f.read_text(errors="ignore")[:6000], meta={"repo": r.name}))
    for cv in ("cv.md", "cv.txt"):
        if (base / cv).exists():
            items.append(Item("cv", "cv", cv, "CV", (base / cv).read_text(errors="ignore")))
    if (base / "cv.pdf").exists():
        try:
            from pypdf import PdfReader
            text = "\n".join(p.extract_text() or "" for p in PdfReader(str(base / "cv.pdf")).pages)
            items.append(Item("cv", "cv", "cv.pdf", "CV", text))
        except Exception:  # noqa: BLE001
            pass
    if (base / "reviews.json").exists():
        for i, r in enumerate(json.loads((base / "reviews.json").read_text())):
            items.append(Item(r.get("review_id", f"review-{i}"), "review", f"reviews.json#{i}", f"Review: {r.get('client', '')}",
                              f"{r.get('client', '')} ({r.get('industry', '')}), {r.get('rating', '')} stars: {r.get('text', '')}",
                              r.get("date"), None, r.get("project"), r.get("industry")))
    if (base / "past_proposals.jsonl").exists():
        for line in (base / "past_proposals.jsonl").read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                items.append(Item(r["proposal_id"], "proposal", f"past_proposals.jsonl#{r['proposal_id']}", r.get("job_title", ""),
                                  r["text"], r.get("date"), r.get("outcome"), (r.get("cited_projects") or [None])[0],
                                  meta={"cited_projects": r.get("cited_projects", [])}))
    return items


class SimpleSearch:
    def __init__(self, items: list[Item]):
        from rank_bm25 import BM25Okapi
        self.items = items
        self.bm = BM25Okapi([TOKEN.findall((i.title + " " + i.text).lower()) or ["_"] for i in items])
        self.dense = None
        try:
            from fastembed import TextEmbedding
            import numpy as np
            self.np = np
            self.model = TextEmbedding("BAAI/bge-small-en-v1.5")
            m = np.array(list(self.model.embed([i.title + "\n" + i.text[:1500] for i in items])))
            self.dense = m / np.linalg.norm(m, axis=1, keepdims=True)
        except Exception:  # noqa: BLE001 - BM25 only
            self.dense = None

    def search(self, query: str, k: int = 5) -> list[tuple[Item, float]]:
        scores = self.bm.get_scores(TOKEN.findall(query.lower()))
        ranked = sorted(range(len(self.items)), key=lambda i: -scores[i])[:30]
        fused = {i: 1 / (60 + r) for r, i in enumerate(ranked)}
        if self.dense is not None:
            q = self.np.array(list(self.model.embed(["Represent this sentence for searching relevant passages: " + query])))[0]
            ds = self.dense @ (q / self.np.linalg.norm(q))
            for r, i in enumerate(self.np.argsort(-ds)[:30]):
                fused[int(i)] = fused.get(int(i), 0) + 1 / (60 + r)
        top = sorted(fused.items(), key=lambda x: -x[1])[:k]
        return [(self.items[i], round(s * 30, 4)) for i, s in top]
