"""Two backends behind the same tools:

* StandaloneBackend - any portfolio folder (PORTFOLIO_DIR); BM25 (+ dense if fastembed installed).
* GigBidBackend     - inside the GigBid repo: the measured RAG pipeline (rag.variant in agent/config.yaml),
                      per-user / per-persona corpora, incremental re-indexing.
"""
from __future__ import annotations

import json
import os
import threading
from collections import Counter
from pathlib import Path

from .corpus import SimpleSearch, load_portfolio


def _filter_ok(item: dict, filters: dict | None) -> bool:
    if not filters:
        return True
    if filters.get("types") and item.get("type") not in filters["types"]:
        return False
    if filters.get("outcomes") and item.get("outcome") not in filters["outcomes"]:
        return False
    if filters.get("since") and (item.get("date") or "0000") < filters["since"]:
        return False
    if filters.get("project") and item.get("project") != filters["project"]:
        return False
    return True


class StandaloneBackend:
    def __init__(self, base: str | Path):
        self.base = Path(base).expanduser()
        self.items = load_portfolio(self.base)
        self.search_index = SimpleSearch(self.items)

    def _out(self, it, score) -> dict:
        return {"evidence_id": it.id, "type": it.type, "source": it.source, "title": it.title, "date": it.date,
                "outcome": it.outcome, "project": it.project, "text": it.text[:1200], "score": score}

    def search(self, requirement: str, k: int, filters: dict | None, user: str | None = None) -> list[dict]:
        res = [self._out(it, s) for it, s in self.search_index.search(requirement, k * 3)]
        return [r for r in res if _filter_ok(r, filters)][:k]

    def get_case(self, case_id: str, user: str | None = None) -> dict | None:
        for it in self.items:
            if it.type == "case_study" and (it.id == case_id or it.project == case_id):
                return {"id": it.id, "title": it.title, "text": it.text, "date": it.date, "client_industry": it.client_industry,
                        "source": it.source, "repo": it.meta.get("repo")}
        return None

    def get_proposal(self, pid: str, user: str | None = None) -> dict | None:
        for it in self.items:
            if it.type == "proposal" and it.id == pid:
                return {"id": it.id, "title": it.title, "text": it.text, "date": it.date, "outcome": it.outcome,
                        "cited_projects": it.meta.get("cited_projects", [])}
        return None

    def get_repo(self, name: str, user: str | None = None) -> dict | None:
        files = {it.source: it.text for it in self.items if it.meta.get("repo") == name}
        return {"name": name, "files": files} if files else None

    def list_skills(self, user: str | None = None) -> list[dict]:
        from collections import Counter
        try:
            from rag.ingest.loaders import extract_skills  # richer lexicon when available
        except Exception:  # noqa: BLE001
            def extract_skills(t):
                return [w for w in ("python", "sql", "react", "typescript", "docker") if w in t.lower()]
        c, ex = Counter(), {}
        for it in self.items:
            for s in extract_skills(it.text):
                c[s] += 1
                ex.setdefault(s, it.project or it.id)
        return [{"skill": s, "mentions": n, "example_item": ex[s]} for s, n in c.most_common(80)]

    def profile(self, user: str | None = None) -> dict:
        p = self.base / "profile.json"
        return json.loads(p.read_text()) if p.exists() else {"portfolio_dir": str(self.base), "items": len(self.items)}


class GigBidBackend:
    """Uses GigBid's RAG stack. `user` is a persona id or 'user:<id>' for an uploaded portfolio."""

    def __init__(self, default_persona: str = "ai_ml_engineer"):
        from agent import settings
        self.settings = settings
        self.default = default_persona
        self._lock = threading.Lock()
        self._retr: dict[str, object] = {}

    def _base(self, user: str) -> Path:
        root = self.settings.ROOT
        if user.startswith("user:"):
            return root / "data" / "user_portfolios" / user.split(":", 1)[1]
        return root / "data" / "personas" / user

    def retriever(self, user: str | None):
        user = user or self.default
        from rag.corpus import Corpus, portfolio_signature
        sig = portfolio_signature(self._base(user))
        with self._lock:
            if user not in self._retr or self._retr[user][0] != sig:   # incremental re-index on portfolio change
                from rag.retriever import variant_class
                cls = variant_class(self.settings.get("rag.variant"))
                corpus = Corpus.from_persona(user, cls.chunking, None, cls.contextual, base=self._base(user))
                self._retr[user] = (sig, cls(user, corpus=corpus))
            return self._retr[user][1]

    def reindex(self, user: str) -> int:
        from rag import corpus as corpus_mod
        with self._lock:
            self._retr.pop(user, None)
            corpus_mod._cached_corpus.cache_clear()
        return len(self.retriever(user).corpus.chunks)

    def search(self, requirement: str, k: int, filters: dict | None, user: str | None = None) -> list[dict]:
        r = self.retriever(user)
        res = r.retrieve(requirement, requirements=[{"id": "q", "text": requirement, "skills": []}], k=max(k * 2, 10))
        items = [e for e in res.items if _filter_ok(e, filters)]
        return items[:k]

    def match(self, job_text: str, requirements: list[dict], k: int, user: str | None = None) -> dict:
        r = self.retriever(user)
        res = r.retrieve(job_text, requirements=requirements or None, k=k)
        return {"items": res.items[: k * 2], "per_requirement": res.per_requirement, "requirements": res.requirements,
                "unsupported_requirements": res.unsupported_requirements, "variant": res.variant, "latency_s": res.latency_s}

    def _docs(self, user: str | None):
        r = self.retriever(user)
        return r.corpus.chunks

    def get_case(self, case_id: str, user: str | None = None) -> dict | None:
        chunks = [c for c in self._docs(user) if c["type"] == "case_study" and (c.get("project") == case_id or c["doc_id"] == case_id)]
        if not chunks:
            return None
        c0 = chunks[0]
        return {"id": c0.get("project") or c0["doc_id"], "title": c0.get("title"), "text": "\n\n".join(c["text"] for c in chunks),
                "date": c0.get("date"), "client_industry": c0.get("client_industry"), "source": c0["source"], "repo": c0.get("repo")}

    def get_proposal(self, pid: str, user: str | None = None) -> dict | None:
        for c in self._docs(user):
            if c["type"] == "proposal" and c.get("item_id") == pid:
                return {"id": pid, "title": c.get("title"), "text": c["text"], "date": c.get("date"), "outcome": c.get("outcome"),
                        "cited_projects": (c.get("extra") or {}).get("cited_projects", [])}
        return None

    def get_repo(self, name: str, user: str | None = None) -> dict | None:
        files = {c["source"]: c["text"] for c in self._docs(user) if c.get("repo") == name and c["type"] in ("readme", "code")}
        return {"name": name, "files": files} if files else None

    def list_skills(self, user: str | None = None) -> list[dict]:
        c, ex = Counter(), {}
        for ch in self._docs(user):
            if ch["type"] == "proposal":
                continue
            for s in ch.get("skills", []):
                c[s] += 1
                ex.setdefault(s, ch.get("project") or ch.get("item_id"))
        return [{"skill": s, "mentions": n, "example_item": ex[s]} for s, n in c.most_common(80)]

    def profile(self, user: str | None = None) -> dict:
        p = self._base(user or self.default) / "profile.json"
        return json.loads(p.read_text()) if p.exists() else {"user": user}


def make_backend():
    if os.environ.get("PORTFOLIO_DIR"):
        return StandaloneBackend(os.environ["PORTFOLIO_DIR"])
    try:
        import agent.settings  # noqa: F401  - running inside the GigBid repo
        return GigBidBackend(os.environ.get("PORTFOLIO_PERSONA", "ai_ml_engineer"))
    except Exception:  # noqa: BLE001
        return StandaloneBackend(Path.cwd())
