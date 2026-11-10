"""V1 requirement decomposition: one dense retrieval per extracted requirement, merged with RRF."""
from __future__ import annotations

from rag.variants.base import Variant


class V1Decomposition(Variant):
    name = "v1_decomposition"

    def search_requirement(self, req, k):
        return self.corpus.dense_search(req["text"], k)
