"""V0 baseline: fixed-size chunks, top-k cosine against the whole job post."""
from __future__ import annotations

import time

from rag.corpus import evidence_from_chunk
from rag.variants.base import RetrievalResult, Variant


class V0Naive(Variant):
    name = "v0_naive"
    chunking = "fixed"

    def retrieve(self, job_text, requirements=None, k=10):
        t0 = time.perf_counter()
        hits = self.corpus.dense_search(job_text[:2000], max(k, 20))
        res = RetrievalResult(self.name, [evidence_from_chunk(self.corpus.by_id[c], s) for c, s in hits], {}, requirements or [])
        res.latency_s = round(time.perf_counter() - t0, 4)
        return res
