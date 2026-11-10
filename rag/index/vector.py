"""Vector indexes. pgvector is the deployed store; the in-memory index (identical cosine maths)
is used by the offline evaluation harness so 600 dev jobs x 8 variants run in minutes."""
from __future__ import annotations

import json
import os

import numpy as np


class MemoryVectorIndex:
    def __init__(self, ids: list[str], matrix: np.ndarray):
        self.ids = ids
        self.m = matrix.astype(np.float32)

    def search(self, qvec: np.ndarray, k: int, mask: np.ndarray | None = None) -> list[tuple[str, float]]:
        s = self.m @ qvec.astype(np.float32)
        if mask is not None:
            s = np.where(mask, s, -1e9)
        k = min(k, len(self.ids))
        idx = np.argpartition(-s, k - 1)[:k]
        idx = idx[np.argsort(-s[idx])]
        return [(self.ids[i], float(s[i])) for i in idx if s[i] > -1e8]


class PgVectorIndex:
    """Chunks + embeddings in Postgres (pgvector). Tenant-scoped by user_id on every query."""

    DDL = """
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE TABLE IF NOT EXISTS portfolio_chunks (
        chunk_id TEXT, user_id TEXT, persona TEXT, collection TEXT, type TEXT, source TEXT, item_id TEXT, project TEXT,
        outcome TEXT, date TEXT, client_industry TEXT, skills TEXT[], text TEXT, meta JSONB,
        embedding vector({dim}), PRIMARY KEY (user_id, collection, chunk_id));
    CREATE INDEX IF NOT EXISTS ix_chunks_user ON portfolio_chunks(user_id, collection);
    """

    def __init__(self, dsn: str | None = None, dim: int = 384):
        import psycopg
        from pgvector.psycopg import register_vector
        self.dsn = dsn or os.environ["DATABASE_URL"]
        self.dim = dim
        self.conn = psycopg.connect(self.dsn, autocommit=True)
        self.conn.execute(self.DDL.format(dim=dim))
        register_vector(self.conn)

    def upsert(self, user_id: str, collection: str, chunks: list[dict], matrix: np.ndarray) -> int:
        with self.conn.cursor() as cur:
            for c, v in zip(chunks, matrix):
                cur.execute(
                    """INSERT INTO portfolio_chunks VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (user_id, collection, chunk_id) DO UPDATE SET text=EXCLUDED.text, embedding=EXCLUDED.embedding,
                       meta=EXCLUDED.meta, skills=EXCLUDED.skills""",
                    (c["chunk_id"], user_id, c["persona"], collection, c["type"], c["source"], c.get("item_id"), c.get("project"),
                     c.get("outcome"), c.get("date"), c.get("client_industry"), c.get("skills", []), c["text"],
                     json.dumps({k: c.get(k) for k in ("title", "repo", "extra", "index", "doc_id")}), v))
        return len(chunks)

    def delete_source(self, user_id: str, collection: str, source: str) -> int:
        cur = self.conn.execute("DELETE FROM portfolio_chunks WHERE user_id=%s AND collection=%s AND source=%s",
                                (user_id, collection, source))
        return cur.rowcount

    def search(self, user_id: str, collection: str, qvec: np.ndarray, k: int) -> list[tuple[str, float]]:
        rows = self.conn.execute(
            "SELECT chunk_id, 1 - (embedding <=> %s) AS score FROM portfolio_chunks WHERE user_id=%s AND collection=%s "
            "ORDER BY embedding <=> %s LIMIT %s", (qvec, user_id, collection, qvec, k)).fetchall()
        return [(r[0], float(r[1])) for r in rows]

    def load_all(self, user_id: str, collection: str) -> tuple[list[dict], np.ndarray]:
        rows = self.conn.execute(
            "SELECT chunk_id, persona, type, source, item_id, project, outcome, date, client_industry, skills, text, meta, embedding "
            "FROM portfolio_chunks WHERE user_id=%s AND collection=%s ORDER BY chunk_id", (user_id, collection)).fetchall()
        chunks, vecs = [], []
        for r in rows:
            meta = r[11] or {}
            chunks.append(dict(chunk_id=r[0], persona=r[1], type=r[2], source=r[3], item_id=r[4], project=r[5], outcome=r[6],
                               date=r[7], client_industry=r[8], skills=list(r[9] or []), text=r[10], **meta))
            vecs.append(np.asarray(r[12], dtype=np.float32))
        return chunks, (np.vstack(vecs) if vecs else np.zeros((0, self.dim), np.float32))
