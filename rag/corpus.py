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
        b = Path(base or PERSONA_DIR / persona)
        return _cached_corpus(persona, chunking, embedder_backend or settings.get("embeddings.backend"), contextual,
                              str(b), portfolio_signature(b))

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


def portfolio_signature(base: Path) -> str:
    """Changes whenever a file is added, removed or edited under the portfolio dir. Part of the corpus cache key, so
    work added in the UI is picked up on the next query; unchanged chunks reuse cached embeddings (incremental)."""
    files = [f for f in Path(base).rglob("*") if f.is_file()] if Path(base).exists() else []
    return f"{len(files)}:{max((f.stat().st_mtime_ns for f in files), default=0)}"


@lru_cache(maxsize=24)
def _cached_corpus(persona: str, chunking: str, embedder_backend: str, contextual: bool, base: str, sig: str = "") -> Corpus:
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
    matrix = _pg_load_or_store(persona, chunking, embedder_backend, contextual, chunks)
    return Corpus(persona, chunks, embedder_backend, contextual=contextual, matrix=matrix)


def _pg_load_or_store(persona: str, chunking: str, embedder_backend: str, contextual: bool, chunks: list[dict]):
    """pgvector is the persistent vector store (GIGBID_PGVECTOR=1): embeddings are written once per collection and
    reloaded on later starts. At ~300 chunks per portfolio similarity is computed in-process over these vectors;
    PgVectorIndex.search is the SQL path for larger collections."""
    if not (env_flag("GIGBID_PGVECTOR") and os.environ.get("DATABASE_URL")):
        return None
    try:
        from rag.embed import get_embedder
        from rag.index.vector import PgVectorIndex
        emb = get_embedder(embedder_backend)
        idx = PgVectorIndex(dim=emb.dim)
        coll = f"{chunking}:{emb.name}:{'ctx' if contextual else 'plain'}"
        stored, mat = idx.load_all(persona, coll)
        if [c["chunk_id"] for c in stored] == sorted(c["chunk_id"] for c in chunks) and len(stored) == len(chunks):
            order = {c["chunk_id"]: i for i, c in enumerate(stored)}
            return mat[[order[c["chunk_id"]] for c in chunks]]
        texts = [((c.get("context") or "") + "\n" if contextual else "") + (f"{c.get('title', '')}\n" if c["type"] in ("code", "readme") else "") + c["text"]
                 for c in chunks]
        # incremental: chunks already stored keep their vectors; only new/changed chunk ids are embedded
        old = {c["chunk_id"]: mat[i] for i, c in enumerate(stored)} if len(stored) else {}
        same = {c["chunk_id"] for c in stored} & {c["chunk_id"] for c in chunks if any(s["chunk_id"] == c["chunk_id"] and s["text"] == c["text"] for s in stored)}
        old = {k: v for k, v in old.items() if k in same}
        todo = [i for i, c in enumerate(chunks) if c["chunk_id"] not in old]
        new = emb.embed([texts[i] for i in todo]) if todo else None
        rows, j = [], 0
        for i, c in enumerate(chunks):
            if c["chunk_id"] in old:
                rows.append(old[c["chunk_id"]])
            else:
                rows.append(new[j])
                j += 1
        mat = np.stack(rows).astype(np.float32) if rows else np.zeros((0, emb.dim), np.float32)
        idx.upsert(persona, coll, chunks, mat)
        return mat
    except Exception as e:  # noqa: BLE001 - fall back to in-memory computation
        import logging
        logging.getLogger("gigbid.rag").warning("pgvector unavailable, computing in memory: %s", e)
        return None


def evidence_from_chunk(c: dict, score: float) -> dict:
    return {"evidence_id": c["chunk_id"], "item_id": c.get("project") or c.get("item_id"), "type": c["type"],
            "source": c["source"], "title": c.get("title", ""), "date": c.get("date"), "outcome": c.get("outcome"),
            "text": c["text"][:1200], "score": round(float(score), 4), "skills": c.get("skills", [])[:12],
            "project": c.get("project"), "repo": c.get("repo"), "cited_projects": (c.get("extra") or {}).get("cited_projects", [])}


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")
