"""V8 corrective / self-RAG loop, implemented as a LangGraph StateGraph:

    retrieve -> grade -> (requery -> grade)* -> finalize

* grade: each requirement's best evidence is scored with the cross-encoder (sigmoid of the logit);
* requery: weak requirements are rewritten (small LLM, or a deterministic expansion offline) and searched again,
  at most `rag.self_rag.max_requery` times;
* finalize: requirements still below threshold get NO evidence - the writer is told it must not claim them.
"""
from __future__ import annotations

import asyncio
import math
import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agent import settings
from rag.corpus import evidence_from_chunk
from rag.embed import get_reranker
from rag.ingest.loaders import extract_skills
from rag.requirements import extract_requirements
from rag.variants.base import RetrievalResult, rrf
from rag.variants.v4_outcome_aware import V4OutcomeAware


class SRState(TypedDict, total=False):
    requirements: list[dict]
    per: dict
    grades: dict
    attempts: int
    rewrites: dict


def sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


class V8SelfRAG(V4OutcomeAware):
    name = "v8_self_rag"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.rr = get_reranker()
        self.threshold = settings.get("rag.self_rag.min_evidence_score", 0.35)
        self.max_requery = settings.get("rag.self_rag.max_requery", 1)
        self.use_llm = self.opts.get("llm_rewrite", False)
        g = StateGraph(SRState)
        g.add_node("retrieve", self._retrieve)
        g.add_node("grade", self._grade)
        g.add_node("requery", self._requery)
        g.add_edge(START, "retrieve")
        g.add_edge("retrieve", "grade")
        g.add_conditional_edges("grade", self._route, {"requery": "requery", "done": END})
        g.add_edge("requery", "grade")
        self.graph = g.compile()

    # ---------------------------------------------------------------- nodes
    def _retrieve(self, s: SRState) -> SRState:
        return {"per": {r["id"]: V4OutcomeAware.search_requirement(self, r, 10) for r in s["requirements"]}, "attempts": 0}

    def _score(self, req_text: str, cid: str) -> float:
        doc = self.corpus._embed_text(self.corpus.by_id[cid])[:1500]
        return sigmoid(self.rr.score(req_text, [doc])[0]) if hasattr(self.rr, "m") else self.rr.score(req_text, [doc])[0]

    def _grade(self, s: SRState) -> SRState:
        grades = {}
        for r in s["requirements"]:
            top = s["per"].get(r["id"], [])[:3]
            best = max((self._score(r["text"], cid) for cid, _ in top), default=0.0)
            grades[r["id"]] = round(best, 4)
        return {"grades": grades}

    def _route(self, s: SRState) -> str:
        weak = [rid for rid, g in s["grades"].items() if g < self.threshold]
        return "requery" if weak and s.get("attempts", 0) < self.max_requery else "done"

    def _rewrite(self, text: str) -> str:
        if self.use_llm:
            from agent.llm import complete, load_prompt
            return asyncio.run(complete("hyde", load_prompt("requery"), text, max_tokens=120))
        skills = extract_skills(text)
        return text + (" " + " ".join(skills) if skills else "") + " project built delivered production"

    def _requery(self, s: SRState) -> SRState:
        per = dict(s["per"])
        rewrites = dict(s.get("rewrites") or {})
        for r in s["requirements"]:
            if s["grades"].get(r["id"], 1) >= self.threshold:
                continue
            q2 = self._rewrite(r["text"])
            rewrites[r["id"]] = q2
            fresh = V4OutcomeAware.search_requirement(self, {**r, "text": q2}, 10)
            per[r["id"]] = rrf([per.get(r["id"], []), fresh])[:10]
        return {"per": per, "rewrites": rewrites, "attempts": s.get("attempts", 0) + 1}

    # ---------------------------------------------------------------- public API
    def retrieve(self, job_text, requirements=None, k=10):
        t0 = time.perf_counter()
        reqs = requirements or extract_requirements(job_text)
        out = self.graph.invoke({"requirements": reqs})
        supported = {rid: lst for rid, lst in out["per"].items() if out["grades"].get(rid, 0) >= self.threshold}
        refused = [rid for rid in out["per"] if rid not in supported]
        merged = rrf(list(supported.values()))[: max(k, 20)] if supported else []
        res = RetrievalResult(self.name, [evidence_from_chunk(self.corpus.by_id[c], sc) for c, sc in merged],
                              {rid: [evidence_from_chunk(self.corpus.by_id[c], sc) for c, sc in lst[:5]]
                               for rid, lst in supported.items()}, reqs, unsupported_requirements=refused,
                              debug={"grades": out["grades"], "rewrites": out.get("rewrites", {}), "attempts": out.get("attempts", 0)})
        res.latency_s = round(time.perf_counter() - t0, 4)
        return res
