"""SQLite persistence and simulated clock for GigSim."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

HERE = Path(__file__).parent
SEED = HERE / "seed_data"

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS accounts (api_key TEXT PRIMARY KEY, account_id TEXT UNIQUE, persona TEXT,
    connects INTEGER, created REAL);
CREATE TABLE IF NOT EXISTS clients (client_id TEXT PRIMARY KEY, data TEXT);
CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, pool TEXT, release_minute REAL, data TEXT);
CREATE TABLE IF NOT EXISTS proposals (proposal_id TEXT PRIMARY KEY, account_id TEXT, job_id TEXT, status TEXT,
    idempotency_key TEXT, payload_hash TEXT, connects_spent INTEGER, created_sim REAL, data TEXT,
    UNIQUE(account_id, idempotency_key));
CREATE TABLE IF NOT EXISTS threads (thread_id TEXT PRIMARY KEY, account_id TEXT, proposal_id TEXT, job_id TEXT,
    client_id TEXT, state TEXT, created_sim REAL);
CREATE TABLE IF NOT EXISTS messages (message_id TEXT PRIMARY KEY, thread_id TEXT, sender TEXT, text TEXT,
    created_sim REAL, idempotency_key TEXT, UNIQUE(thread_id, idempotency_key));
CREATE TABLE IF NOT EXISTS events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT, type TEXT,
    ref_id TEXT, due_sim REAL, processed INTEGER DEFAULT 0, payload TEXT);
CREATE INDEX IF NOT EXISTS ix_events_due ON events(processed, due_sim);
"""


class Store:
    def __init__(self, path: str | None = None):
        self.path = path or os.environ.get("GIGSIM_DB", str(HERE / "var" / "gigsim.db"))
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)

    # ------------------------------------------------------------------ helpers
    def q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self.conn.execute(sql, args).fetchall()

    def x(self, sql: str, args: tuple = ()) -> int:
        with self._lock:
            cur = self.conn.execute(sql, args)
            return cur.lastrowid

    def meta(self, k: str, default: str | None = None) -> str | None:
        r = self.q("SELECT v FROM meta WHERE k=?", (k,))
        return r[0]["v"] if r else default

    def set_meta(self, k: str, v: str) -> None:
        self.x("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))

    # ------------------------------------------------------------------ clock
    def sim_minutes(self) -> float:
        """Simulated minutes since the marketplace opened."""
        start = float(self.meta("clock_start", str(time.time())))
        speed = float(os.environ.get("GIGSIM_SPEED", self.meta("speed", "1.0")))  # sim minutes per real second
        offset = float(self.meta("clock_offset", "0"))
        return (time.time() - start) * speed + offset

    def advance(self, minutes: float) -> float:
        self.set_meta("clock_offset", str(float(self.meta("clock_offset", "0")) + minutes))
        return self.sim_minutes()

    # ------------------------------------------------------------------ seeding
    def seeded(self) -> bool:
        return self.meta("seeded") == "1"

    def seed(self, force: bool = False) -> dict:
        with self._lock:
            if self.seeded() and not force:
                return {"seeded": False}
            for t in ("accounts", "clients", "jobs", "proposals", "threads", "messages", "events", "meta"):
                self.conn.execute(f"DELETE FROM {t}")
            self.set_meta("clock_start", str(time.time()))
            self.set_meta("clock_offset", "0")
            n = {"stream": 0, "dev": 0, "historical": 0}
            for line in open(SEED / "clients.jsonl"):
                c = json.loads(line)
                self.conn.execute("INSERT OR REPLACE INTO clients VALUES(?,?)", (c["client_id"], json.dumps(c)))
            for line in open(SEED / "stream_jobs.jsonl"):
                j = json.loads(line)
                self.conn.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?)",
                                  (j["job_id"], "stream", j.get("release_minute", 0), json.dumps(j)))
                n["stream"] += 1
            for line in open(SEED / "dev_jobs.jsonl"):
                j = json.loads(line)
                self.conn.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?)", (j["job_id"], "dev", -1, json.dumps(j)))
                n["dev"] += 1
            for line in open(SEED / "historical_jobs.jsonl"):
                j = json.loads(line)
                self.conn.execute("INSERT OR REPLACE INTO jobs VALUES(?,?,?,?)",
                                  (j["job_id"], "historical", -10000, json.dumps(j)))
                n["historical"] += 1
            for persona in ("ai_ml_engineer", "fullstack_web_dev", "data_analyst"):
                self.create_account(persona, api_key=f"gs-key-{persona}", account_id=f"acct-{persona}")
            self.set_meta("seeded", "1")
            return {"seeded": True, **n}

    def create_account(self, persona: str, api_key: str, account_id: str) -> dict:
        from .policy import current_policy
        allowance = current_policy(self)["connects"]["weekly_allowance"]
        self.x("INSERT OR IGNORE INTO accounts VALUES(?,?,?,?,?)", (api_key, account_id, persona, allowance, time.time()))
        return {"api_key": api_key, "account_id": account_id, "persona": persona, "connects": allowance}
