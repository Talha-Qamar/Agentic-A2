"""Open embedding and reranking models (CPU).

Backends
* fastembed  - BAAI/bge-small-en-v1.5 (ONNX) embeddings, ms-marco-MiniLM-L-6-v2 cross-encoder
* wordllama  - WordLlama L2 token-embedding model (tiny, ~20 MB)
* hash       - deterministic character n-gram hashing. TEST ONLY (offline unit tests); never reported.
"""
from __future__ import annotations

import hashlib
import os
import re
from functools import lru_cache
from pathlib import Path

import numpy as np

from agent import settings

CACHE = settings.ROOT / "data" / "processed" / "emb_cache"


def _norm(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1
    return (m / n).astype(np.float32)


class Embedder:
    name: str
    dim: int

    def embed(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError

    def embed_cached(self, texts: list[str]) -> np.ndarray:
        CACHE.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha1((self.name + "\x00".join(texts)).encode()).hexdigest()[:20]
        f = CACHE / f"{key}.npy"
        if f.exists():
            return np.load(f)
        m = self.embed(texts)
        np.save(f, m)
        return m


class FastEmbedder(Embedder):
    def __init__(self, model: str):
        from fastembed import TextEmbedding
        self.name = f"fastembed:{model}"
        self.m = TextEmbedding(model, threads=int(os.environ.get("EMBED_THREADS", "2")))
        self.dim = len(next(iter(self.m.embed(["x"]))))
        self.query_prefix = "Represent this sentence for searching relevant passages: " if "bge" in model else ""

    def embed(self, texts):
        return _norm(np.array(list(self.m.embed(texts, batch_size=32))))

    def embed_query(self, texts):
        return _norm(np.array(list(self.m.embed([self.query_prefix + t for t in texts]))))


class WordLlamaEmbedder(Embedder):
    def __init__(self):
        from wordllama import WordLlama
        self.name = "wordllama:l2_supercat_256"
        self.m = WordLlama.load(dim=256)
        self.dim = 256

    def embed(self, texts):
        return _norm(np.asarray(self.m.embed(texts), dtype=np.float32))


class HashEmbedder(Embedder):
    """Deterministic n-gram hashing. For offline tests only."""
    def __init__(self, dim: int = 384):
        self.name = f"hash:{dim}"
        self.dim = dim

    def embed(self, texts):
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, t in enumerate(texts):
            toks = re.findall(r"[a-z0-9.+#-]+", t.lower())
            grams = toks + [a + "_" + b for a, b in zip(toks, toks[1:])]
            for g in grams:
                h = int(hashlib.md5(g.encode()).hexdigest()[:8], 16)
                out[i, h % self.dim] += 1.0 if h & 1 else -1.0
        return _norm(out)


@lru_cache(maxsize=4)
def get_embedder(backend: str | None = None) -> Embedder:
    backend = backend or settings.get("embeddings.backend", "fastembed")
    if backend == "fastembed":
        return FastEmbedder(settings.get("embeddings.model"))
    if backend == "wordllama":
        return WordLlamaEmbedder()
    if backend == "hash":
        return HashEmbedder()
    raise ValueError(f"unknown embedder {backend}")


def embed_queries(emb: Embedder, texts: list[str]) -> np.ndarray:
    if hasattr(emb, "embed_query"):
        return emb.embed_query(texts)
    return emb.embed(texts)


class Reranker:
    def score(self, query: str, docs: list[str]) -> list[float]:
        raise NotImplementedError


class CrossEncoderReranker(Reranker):
    def __init__(self, model: str):
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        self.name = model
        self.m = TextCrossEncoder(model, threads=int(os.environ.get("EMBED_THREADS", "2")))

    def score(self, query, docs):
        return [float(s) for s in self.m.rerank(query, docs, batch_size=16)]


class OverlapReranker(Reranker):
    """Token-overlap scorer. For offline tests only."""
    name = "overlap"

    def score(self, query, docs):
        q = set(re.findall(r"\w+", query.lower()))
        return [len(q & set(re.findall(r"\w+", d.lower()))) / (len(q) or 1) for d in docs]


@lru_cache(maxsize=2)
def get_reranker(backend: str | None = None) -> Reranker:
    backend = backend or os.environ.get("GIGBID_RERANKER", settings.get("reranker.backend", "fastembed"))
    if backend == "fastembed":
        return CrossEncoderReranker(settings.get("reranker.model"))
    return OverlapReranker()


def model_dir_ready() -> bool:
    p = Path(os.environ.get("FASTEMBED_CACHE_PATH", Path.home() / ".cache" / "fastembed"))
    return p.exists() and any(p.iterdir())
