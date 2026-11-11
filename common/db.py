"""Postgres access (psycopg 3) and schema. Every tenant-owned table has user_id and every query filters on it."""
from __future__ import annotations

import json
import os
import threading
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None
_lock = threading.Lock()

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT, password_hash TEXT NOT NULL,
  persona TEXT NOT NULL DEFAULT 'ai_ml_engineer', marketplace_mode TEXT NOT NULL DEFAULT 'gigsim',
  gigsim_key TEXT, settings JSONB NOT NULL DEFAULT '{}'::jsonb, onboarded BOOLEAN NOT NULL DEFAULT false,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS oauth_tokens (
  user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, provider TEXT NOT NULL,
  ciphertext BYTEA NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (user_id, provider));
CREATE TABLE IF NOT EXISTS saved_searches (
  search_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE, query TEXT NOT NULL,
  category TEXT, interval_minutes INT NOT NULL DEFAULT 30, enabled BOOLEAN NOT NULL DEFAULT true,
  last_run_at TIMESTAMPTZ, last_seen_minute DOUBLE PRECISION);
CREATE TABLE IF NOT EXISTS jobs (
  user_id TEXT NOT NULL, job_id TEXT NOT NULL, title TEXT, data JSONB NOT NULL, dedup_key TEXT, duplicate_of TEXT,
  status TEXT NOT NULL DEFAULT 'queued', thread_id TEXT, fit_score DOUBLE PRECISION, risk_score DOUBLE PRECISION,
  action TEXT, price DOUBLE PRECISION, connects_cost INT, summary JSONB, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (user_id, job_id));
CREATE INDEX IF NOT EXISTS ix_jobs_dedup ON jobs(user_id, dedup_key);
CREATE TABLE IF NOT EXISTS runs (
  thread_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL, job_id TEXT, conversation_id TEXT,
  status TEXT NOT NULL, status_reason TEXT, trace_id TEXT, tokens INT DEFAULT 0, cost_usd DOUBLE PRECISION DEFAULT 0,
  latency_s DOUBLE PRECISION, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS run_events (
  id BIGSERIAL PRIMARY KEY, thread_id TEXT NOT NULL, user_id TEXT NOT NULL, ts TIMESTAMPTZ NOT NULL DEFAULT now(),
  node TEXT, kind TEXT NOT NULL, payload JSONB);
CREATE INDEX IF NOT EXISTS ix_run_events_thread ON run_events(thread_id, id);
CREATE TABLE IF NOT EXISTS approvals (
  approval_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, thread_id TEXT NOT NULL, kind TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending', payload JSONB NOT NULL, decision JSONB, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  decided_at TIMESTAMPTZ);
CREATE INDEX IF NOT EXISTS ix_approvals_user ON approvals(user_id, status);
CREATE TABLE IF NOT EXISTS pipeline (
  user_id TEXT NOT NULL, proposal_id TEXT NOT NULL, job_id TEXT, title TEXT, stage TEXT NOT NULL, category TEXT,
  connects_spent INT DEFAULT 0, bid_amount DOUBLE PRECISION, thread_id TEXT, marketplace_thread_id TEXT,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), data JSONB, PRIMARY KEY (user_id, proposal_id));
CREATE TABLE IF NOT EXISTS conversations (
  user_id TEXT NOT NULL, marketplace_thread_id TEXT NOT NULL, proposal_id TEXT, job_id TEXT, last_message_id TEXT,
  graph_thread_id TEXT, state TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY (user_id, marketplace_thread_id));
CREATE TABLE IF NOT EXISTS edits (
  id BIGSERIAL PRIMARY KEY, user_id TEXT NOT NULL, thread_id TEXT, before_text TEXT, after_text TEXT, diff JSONB,
  candidates JSONB, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS memory_candidates (
  user_id TEXT NOT NULL, kind TEXT NOT NULL, key TEXT NOT NULL, value JSONB, occurrences INT NOT NULL DEFAULT 1,
  edit_ids BIGINT[] NOT NULL DEFAULT '{}', promoted BOOLEAN NOT NULL DEFAULT false, updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, kind, key));
CREATE TABLE IF NOT EXISTS audit_log (
  id BIGSERIAL PRIMARY KEY, ts TIMESTAMPTZ NOT NULL DEFAULT now(), user_id TEXT, server TEXT NOT NULL, tool TEXT NOT NULL,
  arguments JSONB, result JSONB, status TEXT, trace_id TEXT);
CREATE OR REPLACE FUNCTION audit_log_append_only() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'audit_log is append-only'; END; $$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS audit_log_no_update ON audit_log;
CREATE TRIGGER audit_log_no_update BEFORE UPDATE OR DELETE ON audit_log FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();
CREATE TABLE IF NOT EXISTS calendar_events (
  event_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, start_ts TIMESTAMPTZ NOT NULL, end_ts TIMESTAMPTZ NOT NULL,
  title TEXT, kind TEXT NOT NULL DEFAULT 'busy', idempotency_key TEXT, data JSONB, UNIQUE(user_id, idempotency_key));
CREATE TABLE IF NOT EXISTS email_drafts (
  draft_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, to_alias TEXT, subject TEXT, body TEXT, idempotency_key TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), UNIQUE(user_id, idempotency_key));
CREATE TABLE IF NOT EXISTS panel_votes (
  id BIGSERIAL PRIMARY KEY, pair_id TEXT NOT NULL, rater TEXT NOT NULL, choice TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(pair_id, rater));
CREATE TABLE IF NOT EXISTS judge_labels (
  item_id TEXT PRIMARY KEY, label DOUBLE PRECISION NOT NULL, labeller TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
"""


def dsn() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://gigbid:gigbid@localhost:5432/gigbid")


def pool() -> ConnectionPool:
    global _pool
    with _lock:
        if _pool is None:
            _pool = ConnectionPool(dsn(), min_size=1, max_size=int(os.environ.get("DB_POOL_MAX", "8")),
                                   kwargs={"autocommit": True, "row_factory": dict_row}, open=True)
            import atexit
            atexit.register(lambda: _pool.close(timeout=1) if _pool else None)
        return _pool


@contextmanager
def conn():
    with pool().connection() as c:
        yield c


def q(sql: str, args: tuple | dict = ()) -> list[dict]:
    with conn() as c:
        cur = c.execute(sql, args)
        return cur.fetchall() if cur.description else []


def x(sql: str, args: tuple | dict = ()) -> int:
    with conn() as c:
        return c.execute(sql, args).rowcount


def one(sql: str, args: tuple | dict = ()) -> dict | None:
    r = q(sql, args)
    return r[0] if r else None


def init_schema() -> None:
    with psycopg.connect(dsn(), autocommit=True) as c:
        c.execute(SCHEMA)


def jdump(o) -> str:
    return json.dumps(o, default=str)
