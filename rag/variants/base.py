"""Shared machinery for retrieval variants. Every variant returns the same RetrievalResult shape."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from rag.corpus import Corpus, evidence_from_chunk
from rag.requirements import extract_requirements


@dataclass
class RetrievalResult:
    variant: str
    items: list[dict]                                   # merged, ranked evidence (chunk level)
    per_requirement: dict[str, list[dict]] = field(default_factory=dict)
    requirements: list[dict] = field(default_factory=list)
    unsupported_requirements: list[str] = field(default_factory=list)   # V8 refusals
    debug: dict = field(default_factory=dict)
    latency_s: float = 0.0

    def ranked_items(self) -> list[str]:
        """Distinct evidence items (projects / repos / proposals) in rank order."""
        seen, out = set(), []
        for e in self.items:
            key = e.get("item_id") or e["evidence_id"]
            if key not in seen:
                seen.add(key)
                out.append(key)
        return out


def rrf(ranked_lists: list[list[tuple[str, float]]], k: int = 60) -> list[tuple[str, float]]:
    scores: dict[str, float] = {}
    for lst in ranked_lists:
        for rank, (cid, _) in enumerate(lst):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: -x[1])


def minmax(pairs: list[tuple[str, float]]) -> list[tuple[str, float]]:
    if not pairs:
        return pairs
    vals = [s for _, s in pairs]
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9:
        return [(c, 1.0) for c, _ in pairs]
    return [(c, (s - lo) / (hi - lo)) for c, s in pairs]


class Variant:
    name = "base"
    chunking = "structured"
    contextual = False
    uses_llm = False

    def __init__(self, persona: str, embedder: str | None = None, corpus: Corpus | None = None, **opts):
        self.persona = persona
        self.opts = opts
        self.corpus = corpus or Corpus.from_persona(persona, self.chunking, embedder, self.contextual)

    # subclasses implement per-requirement retrieval
    def search_requirement(self, req: dict, k: int) -> list[tuple[str, float]]:
        raise NotImplementedError

    def retrieve(self, job_text: str, requirements: list[dict] | None = None, k: int = 10) -> RetrievalResult:
        t0 = time.perf_counter()
        reqs = requirements or extract_requirements(job_text)
        per: dict[str, list[tuple[str, float]]] = {}
        for r in reqs:
            per[r["id"]] = self.search_requirement(r, max(k, 10))
        merged = self.merge(per, k)
        res = RetrievalResult(self.name, [self.evidence(c, s) for c, s in merged],
                              {rid: [self.evidence(c, s) for c, s in lst[:5]] for rid, lst in per.items()},
                              reqs)
        res.latency_s = round(time.perf_counter() - t0, 4)
        return res

    def evidence(self, cid: str, score: float) -> dict:
        """Evidence item with the skills of its whole project (skill graph), not just of the one chunk shown."""
        c = self.corpus.by_id[cid]
        e = evidence_from_chunk(c, score)
        item = c.get("project") or c.get("item_id")
        if c["type"] != "proposal" and item:
            e["skills"] = sorted(set(e["skills"]) | self.corpus.graph.item_skills.get(item, set()))[:24]
        return e

    def merge(self, per: dict[str, list[tuple[str, float]]], k: int) -> list[tuple[str, float]]:
        """Fuse per-requirement lists with RRF so every requirement contributes evidence."""
        return rrf(list(per.values()))[: max(k, 20)]
