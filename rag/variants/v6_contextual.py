"""V6 contextual retrieval: a generated context line is prepended to each chunk before indexing
(LLM-generated when data/processed/contexts/<persona>.json exists, template otherwise); hybrid search."""
from __future__ import annotations

from rag.variants.v2_hybrid import V2Hybrid


class V6Contextual(V2Hybrid):
    name = "v6_contextual"
    contextual = True
