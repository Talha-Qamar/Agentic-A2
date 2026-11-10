"""Retriever factory: the deployed variant is chosen in agent/config.yaml (rag.variant), which is set
from the evaluation in evals/results/rag_benchmark.json - not by default."""
from __future__ import annotations

from functools import lru_cache

from agent import settings

VARIANTS = {
    "v0_naive": "rag.variants.v0_naive:V0Naive",
    "v1_decomposition": "rag.variants.v1_decomposition:V1Decomposition",
    "v2_hybrid": "rag.variants.v2_hybrid:V2Hybrid",
    "v3_rerank": "rag.variants.v3_rerank:V3Rerank",
    "v4_outcome_aware": "rag.variants.v4_outcome_aware:V4OutcomeAware",
    "v5_multivector": "rag.variants.v5_multivector:V5MultiVector",
    "v6_contextual": "rag.variants.v6_contextual:V6Contextual",
    "v7_hyde": "rag.variants.v7_hyde:V7HyDE",
    "v8_self_rag": "rag.variants.v8_self_rag:V8SelfRAG",
    "v9_skill_graph": "rag.variants.v9_skill_graph:V9SkillGraph",
}


def variant_class(name: str):
    mod, cls = VARIANTS[name].split(":")
    return getattr(__import__(mod, fromlist=[cls]), cls)


@lru_cache(maxsize=32)
def get_retriever(persona: str, variant: str | None = None, embedder: str | None = None):
    name = variant or settings.get("rag.variant", "v3_rerank")
    return variant_class(name)(persona, embedder=embedder)


def reset_cache() -> None:
    """Called after incremental re-indexing so the next query sees new portfolio items."""
    from rag import corpus
    get_retriever.cache_clear()
    corpus._cached_corpus.cache_clear()
