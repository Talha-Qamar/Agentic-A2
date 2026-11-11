"""B1: adding work to a portfolio is picked up by the next query, and only the new chunks are embedded."""
import shutil
import uuid
from pathlib import Path

from mcp_servers.portfolio.backend import GigBidBackend

ROOT = Path(__file__).resolve().parents[2]


def test_new_case_study_is_indexed_incrementally(tmp_path, monkeypatch):
    base = tmp_path / "data" / "user_portfolios" / "u1"
    shutil.copytree(ROOT / "data/personas/data_analyst", base)
    be = GigBidBackend("data_analyst")
    monkeypatch.setattr(be, "_base", lambda user: base)
    n0 = len(be.retriever("user:u1").corpus.chunks)
    (base / "case_studies" / "new.md").write_text("---\nproject: new-1\n---\n# Case study: Zebrafish telemetry\n\n"
                                                   f"I built a zebrafish telemetry dashboard in Grafana with 14 panels (run {uuid.uuid4().hex}).")
    from rag.embed import HashEmbedder
    seen = []
    orig = HashEmbedder.embed
    monkeypatch.setattr(HashEmbedder, "embed", lambda self, texts: (seen.extend(texts), orig(self, texts))[1])
    r = be.retriever("user:u1")
    assert len(r.corpus.chunks) > n0
    corpus_texts = [t for t in seen if "Zebrafish" in t or "zebrafish" in t]
    assert corpus_texts and len([t for t in seen if len(t) > 60]) <= 3   # only the new chunk(s), not ~280
    hits = be.search("zebrafish telemetry dashboard", 3, None, user="user:u1")
    assert "Zebrafish" in hits[0]["text"]
