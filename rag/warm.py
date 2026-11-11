"""Pre-build every persona corpus for the deployed retrieval variant (Docker build / startup), so the first user
request does not pay for embedding the portfolio.    python -m rag.warm"""
from __future__ import annotations

import time

from agent import settings
from rag.corpus import Corpus
from rag.retriever import variant_class

if __name__ == "__main__":
    cls = variant_class(settings.get("rag.variant"))
    for p in ("ai_ml_engineer", "fullstack_web_dev", "data_analyst"):
        t = time.time()
        c = Corpus.from_persona(p, cls.chunking, None, cls.contextual)
        print(f"{p}: {len(c.chunks)} chunks in {time.time() - t:.1f}s")
    if cls.__name__.startswith(("V3", "V4", "V8")):
        from rag.embed import get_reranker
        get_reranker().score("warm", ["up"])
        print("reranker ready")
