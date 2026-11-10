"""V2 hybrid: BM25 + dense per requirement, fused with reciprocal rank fusion (exact names like Celery, dbt)."""
from __future__ import annotations

from rag.variants.base import Variant, rrf


class V2Hybrid(Variant):
    name = "v2_hybrid"

    def search_requirement(self, req, k):
        q = req["text"]
        return rrf([self.corpus.dense_search(q, 30), self.corpus.bm25_search(q, 30)])[:k]
