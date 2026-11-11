"""V9 skill graph: requirement -> skills -> projects (optionally filtered by client industry) -> best chunk.

Ablation switches (opts): decomposition (per-requirement queries), outcome_boost (proposal outcomes on graph items),
dense_tiebreak (embedding similarity to pick/order chunks), hybrid_fallback (BM25+dense when a requirement names no
known skill), rerank (add a cross-encoder pass - tested because it hurt V3).
"""
from __future__ import annotations

from rag.ingest.loaders import extract_skills
from rag.variants.base import Variant, rrf


class V9SkillGraph(Variant):
    name = "v9_skill_graph"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.o = {"decomposition": True, "outcome_boost": True, "dense_tiebreak": True, "hybrid_fallback": True, "rerank": False} | {
            k: v for k, v in self.opts.items() if k in ("decomposition", "outcome_boost", "dense_tiebreak", "hybrid_fallback", "rerank")}

    def retrieve(self, job_text, requirements=None, k=10):
        if not self.o["decomposition"]:
            requirements = [{"id": "r1", "text": job_text[:2000], "skills": []}]
        return super().retrieve(job_text, requirements, k)

    def search_requirement(self, req, k):
        q = req["text"]
        skills = extract_skills(q) + req.get("skills", [])
        items = self.corpus.graph.items_for(skills, self.opts.get("industry"))
        if not self.o["outcome_boost"]:
            base = {}
            for s in skills:
                from rag.index.graph import canon
                its = self.corpus.graph.skill_items.get(canon(s), set())
                for it in its:
                    base[it] = base.get(it, 0) + 1.0 / (1 + len(its)) ** 0.5
            items = sorted(base.items(), key=lambda x: -x[1])
        items = items[:k]
        qv = self.corpus.qvec([q])[0] if self.o["dense_tiebreak"] else None
        out = []
        for item, gscore in items:
            cids = self.corpus.graph.item_chunks.get(item, [])
            if not cids:
                continue
            if qv is not None:
                sims = [(cid, float(self.corpus.matrix[self.corpus.ids.index(cid)] @ qv)) for cid in cids[:40]]
                best = max(sims, key=lambda x: x[1])
                out.append((best[0], gscore + 0.1 * best[1]))
            else:
                out.append((cids[0], gscore))
        if not out and self.o["hybrid_fallback"]:
            out = rrf([self.corpus.dense_search(q, 20), self.corpus.bm25_search(q, 20)])[:k]
        if self.o["rerank"] and out:
            from rag.embed import get_reranker
            sc = get_reranker().score(q, [self.corpus.by_id[c]["text"][:1500] for c, _ in out])
            out = sorted(zip([c for c, _ in out], sc), key=lambda x: -x[1])
        return out
