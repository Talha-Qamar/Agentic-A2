"""V9 skill graph: requirement -> skills -> projects (optionally filtered by client industry) -> best chunk."""
from __future__ import annotations

from rag.ingest.loaders import extract_skills
from rag.variants.base import Variant, rrf


class V9SkillGraph(Variant):
    name = "v9_skill_graph"

    def search_requirement(self, req, k):
        q = req["text"]
        skills = extract_skills(q) + req.get("skills", [])
        items = self.corpus.graph.items_for(skills, self.opts.get("industry"))[:k]
        qv = self.corpus.qvec([q])[0]
        out = []
        for item, gscore in items:
            cids = self.corpus.graph.item_chunks.get(item, [])
            if not cids:
                continue
            sims = [(cid, float(self.corpus.matrix[self.corpus.ids.index(cid)] @ qv)) for cid in cids[:40]]
            best = max(sims, key=lambda x: x[1])
            out.append((best[0], gscore + 0.1 * best[1]))
        # fall back to hybrid search when the requirement names no known skill
        if not out:
            out = rrf([self.corpus.dense_search(q, 20), self.corpus.bm25_search(q, 20)])[:k]
        return out
