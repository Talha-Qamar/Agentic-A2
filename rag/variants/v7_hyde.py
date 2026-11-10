"""V7 HyDE: retrieve with a hypothetical ideal proposal paragraph written by a small LLM."""
from __future__ import annotations

import asyncio
import time

from rag.corpus import evidence_from_chunk
from rag.variants.base import RetrievalResult, rrf
from rag.variants.v2_hybrid import V2Hybrid


def hyde_document(job_text: str) -> str:
    from agent.guardrails import wrap_untrusted
    from agent.llm import complete, load_prompt
    return asyncio.run(complete("hyde", load_prompt("hyde"), wrap_untrusted(job_text[:3000]), max_tokens=350))


class V7HyDE(V2Hybrid):
    name = "v7_hyde"
    uses_llm = True

    def retrieve(self, job_text, requirements=None, k=10):
        t0 = time.perf_counter()
        hyde = self.opts.get("hyde_doc") or hyde_document(job_text)
        dense = self.corpus.dense_search(hyde, 40)
        base = super().retrieve(job_text, requirements, k)
        fused = rrf([dense, [(e["evidence_id"], e["score"]) for e in base.items]])[: max(k, 20)]
        res = RetrievalResult(self.name, [evidence_from_chunk(self.corpus.by_id[c], s) for c, s in fused],
                              base.per_requirement, base.requirements, debug={"hyde": hyde[:600]})
        res.latency_s = round(time.perf_counter() - t0, 4)
        return res
