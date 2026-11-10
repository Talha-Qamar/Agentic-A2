"""A persona's (or user's) indexed portfolio: documents -> chunks -> dense + BM25 + skill graph.

    corpus = Corpus.from_persona("ai_ml_engineer", chunking="structured")

Built from disk for evaluation, or from pgvector rows for a live user (Corpus.from_rows).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np

from agent import settings
from rag.embed import embed_queries, get_embedder
from rag.index.bm25 import BM25Index
from rag.index.graph import SkillGraph
from rag.index.vector import MemoryVectorIndex
from rag.ingest import chunkers
from rag.ingest.loaders import load_persona_dir

PERSONA_DIR = settings.ROOT / "data" / "personas"
CONTEXT_DIR = settings.ROOT / "data" / "processed" / "contexts"


def template_context(c: dict) -> str:
    """Deterministic context line (fallback when no LLM-generated context is cached)."""
    kind = {"case_study": "case study", "readme": "repository README", "code": "source file", "cv": "CV",
            "review": "client review", "proposal": "past proposal"}.get(c["type"], c["type"])
    bits = [f"From the freelancer's {kind}", f"'{c.get('title', '')}'"]
    if c.get("repo"):
        bits.append(f"(repository {c['repo']})")
    if c.get("client_industry"):
        bits.append(f"for a {c['client_industry']} client")
    if c.get("outcome"):
        bits.append(f"outcome: {c['outcome']}")
    return " ".join(bits) + "."


class Corpus:
    def __init__(self, persona: str, chunks: list[dict], embedder_backend: str | None = None, contextual: bool = False,
                 matrix: np.ndarray | None = None):
        self.persona = persona
        self.chunks = chunks
        self.by_id = {c["chunk_id"]: c for c in chunks}
        self.ids = [c["chunk_id"] for c in chunks]
        self.contextual = contextual
        self.embedder = get_embedder(embedder_backend)
        texts = [self._embed_text(c) for c in chunks]
        if matrix is None:
            matrix = self.embedder.embed_cached(texts) if texts else np.zeros((0, self.embedder.dim), np.float32)
        self.matrix = matrix
        self.dense = MemoryVectorIndex(self.ids, matrix)
        self.bm25 = BM25Index(self.ids, texts)
        self.graph = SkillGraph(chunks)
        self.types = np.array([c["type"] for c in chunks])
        self._win_rate = self._project_outcomes()

    def _embed_text(self, c: dict) -> str:
        head = f"{c.get('title', '')}\n" if c["type"] in ("code", "readme") else ""
        return ((c.get("context") or "") + "\n" if self.contextual else "") + head + c["text"]

    @classmethod
    def from_persona(cls, persona: str, chunking: str = "structured", embedder_backend: str | None = None,
                     contextual: bool = False, base: Path | None = None) -> "Corpus":
        return _cached_corpus(persona, chunking, embedder_backend or settings.get("embeddings.backend"), contextual,
                              str(base or PERSONA_DIR / persona))

    @classmethod
    def from_rows(cls, persona: str, chunks: list[dict], matrix: np.ndarray, embedder_backend: str | None = None) -> "Corpus":
        return cls(persona, chunks, embedder_backend, matrix=matrix)

    # --------------------------------------------------------------- search primitives
    def qvec(self, texts: list[str]) -> np.ndarray:
        return embed_queries(self.embedder, texts)

    def mask(self, types: tuple[str, ...] | None) -> np.ndarray | None:
        return None if not types else np.isin(self.types, list(types))

    def dense_search(self, query: str, k: int, types: tuple[str, ...] | None = None, qv: np.ndarray | None = None):
        v = qv if qv is not None else self.qvec([query])[0]
        return self.dense.search(v, k, self.mask(types))

    def bm25_search(self, query: str, k: int, types: tuple[str, ...] | None = None):
        return self.bm25.search(query, k, self.mask(types))

    def _project_outcomes(self) -> dict[str, float]:
        stats: dict[str, list[int]] = {}
        for c in self.chunks:
            if c["type"] == "proposal":
                for p in (c.get("extra") or {}).get("cited_projects", []):
                    stats.setdefault(p, []).append(1 if c.get("outcome") in ("won", "replied") else 0)
        return {p: sum(v) / len(v) for p, v in stats.items() if v}

    def project_win_rate(self, project: str | None) -> float | None:
        return self._win_rate.get(project) if project else None


@lru_cache(maxsize=24)
def _cached_corpus(persona: str, chunking: str, embedder_backend: str, contextual: bool, base: str) -> Corpus:
    docs = load_persona_dir(Path(base), persona)
    if chunking == "fixed":
        chs = chunkers.fixed(docs, settings.get("rag.chunk_chars", 900), settings.get("rag.chunk_overlap", 150))
    else:
        chs = chunkers.structured(docs)
    chunks = [c.to_dict() for c in chs]
    if contextual:
        cache = CONTEXT_DIR / f"{persona}.json"
        llm_ctx = json.loads(cache.read_text()) if cache.exists() else {}
        for c in chunks:
            c["context"] = llm_ctx.get(c["chunk_id"]) or template_context(c)
            c["context_source"] = "llm" if c["chunk_id"] in llm_ctx else "template"
    return Corpus(persona, chunks, embedder_backend, contextual=contextual)


def evidence_from_chunk(c: dict, score: float) -> dict:
    return {"evidence_id": c["chunk_id"], "item_id": c.get("project") or c.get("item_id"), "type": c["type"],
            "source": c["source"], "title": c.get("title", ""), "date": c.get("date"), "outcome": c.get("outcome"),
            "text": c["text"][:1200], "score": round(float(score), 4), "skills": c.get("skills", [])[:12],
            "project": c.get("project"), "repo": c.get("repo"), "cited_projects": (c.get("extra") or {}).get("cited_projects", [])}


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")
