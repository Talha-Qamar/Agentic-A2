"""LangGraph store (long-term memory). Postgres in production, in-memory for tests (GIGBID_MEMORY=memory)."""
from __future__ import annotations

import os
import threading

_store = None
_lock = threading.Lock()


def get_store():
    global _store
    with _lock:
        if _store is None:
            if os.environ.get("GIGBID_MEMORY") == "memory" or not os.environ.get("DATABASE_URL"):
                from langgraph.store.memory import InMemoryStore
                _store = InMemoryStore()
            else:
                import psycopg
                from langgraph.store.postgres import PostgresStore
                from psycopg.rows import dict_row
                conn = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, prepare_threshold=0, row_factory=dict_row)
                _store = PostgresStore(conn)
                _store.setup()
        return _store


def ns(user_id: str, kind: str) -> tuple[str, ...]:
    return ("memory", user_id, kind)


def list_items(user_id: str, kind: str) -> list[dict]:
    return [{"key": it.key, **it.value} for it in get_store().search(ns(user_id, kind), limit=100)]


def delete_item(user_id: str, kind: str, key: str) -> None:
    get_store().delete(ns(user_id, kind), key)
