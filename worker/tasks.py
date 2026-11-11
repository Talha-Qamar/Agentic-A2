"""Background work (E1): scouting, analysis, resumes, conversations and pipeline sync run here, never inside a
web request.  Arq (Redis) executes these in the `worker` service; tests and the single-process Render deployment
run the same functions through `enqueue()` fallbacks.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time

from agent import settings
from common import db

log = logging.getLogger("gigbid.worker")


# ------------------------------------------------------------------ helpers
def user_row(user_id: str) -> dict:
    u = db.one("SELECT * FROM users WHERE user_id=%s", (user_id,))
    if not u:
        raise ValueError(f"unknown user {user_id}")
    s = u.get("settings") or {}
    return {"user_id": u["user_id"], "persona": u["persona"], "gigsim_key": u["gigsim_key"], "marketplace_mode": u["marketplace_mode"],
            "settings": {k: s[k] for k in ("hourly_floor", "target_rate") if k in s} | {"autonomy": s.get("autonomy", "suggest")},
            "own_portfolio": bool(s.get("own_portfolio"))}


def emitter(thread_id: str, user_id: str):
    def emit(node: str, kind: str, payload: dict) -> None:
        try:
            db.x("INSERT INTO run_events(thread_id, user_id, node, kind, payload) VALUES (%s,%s,%s,%s,%s)",
                 (thread_id, user_id, node, kind, json.dumps(payload, default=str)[:8000]))
        except Exception as e:  # noqa: BLE001
            log.warning("emit failed: %s", e)
    return emit


def dedup_key(job: dict) -> str:
    t = re.sub(r"\W+", " ", (job.get("title") or "").lower())
    t = re.sub(r"\b(reposted|urgent)\b", "", t).strip()
    d = re.sub(r"\W+", " ", (job.get("snippet") or job.get("description") or "").lower())[:160]
    d = d.replace("we re", "we are")
    return hashlib.sha1(f"{t}|{d}".encode()).hexdigest()[:16]


async def port_for(user: dict, servers=("marketplace",)):
    from agent.mcp_client import load_tools
    from agent.marketplace_port import McpMarketplace
    from common.tokens import mint_mcp_token
    tools = await load_tools(user["user_id"], mint_mcp_token(user["user_id"], user["persona"], user.get("gigsim_key"),
                                                            user.get("marketplace_mode", "gigsim")), servers=servers)
    return McpMarketplace(tools)


def record_run(thread_id: str, user_id: str, kind: str, job_id: str | None, out: dict, conversation_id: str | None = None) -> None:
    db.x("""INSERT INTO runs(thread_id, user_id, kind, job_id, conversation_id, status, status_reason, trace_id, tokens, cost_usd, latency_s)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (thread_id) DO UPDATE SET status=EXCLUDED.status,
            status_reason=EXCLUDED.status_reason, tokens=runs.tokens+EXCLUDED.tokens, cost_usd=runs.cost_usd+EXCLUDED.cost_usd,
            latency_s=COALESCE(runs.latency_s,0)+EXCLUDED.latency_s, updated_at=now()""",
         (thread_id, user_id, kind, job_id, conversation_id, out.get("status"), out.get("status_reason"), out.get("trace_id"),
          out.get("tokens", 0), out.get("cost_usd", 0.0), out.get("latency_s", 0.0)))
    if out.get("pending_approval"):
        p = out["pending_approval"]
        aid = f"ap-{thread_id}-{len(db.q('SELECT 1 FROM approvals WHERE thread_id=%s', (thread_id,)))}"
        db.x("UPDATE approvals SET status='superseded' WHERE thread_id=%s AND status='pending'", (thread_id,))
        db.x("INSERT INTO approvals(approval_id, user_id, thread_id, kind, payload) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
             (aid, user_id, thread_id, p.get("type", "approval"), json.dumps(p, default=str)))
    db.x("INSERT INTO run_events(thread_id, user_id, node, kind, payload) VALUES (%s,%s,%s,%s,%s)",
         (thread_id, user_id, "run", "run_end", json.dumps({k: out.get(k) for k in ("status", "status_reason", "tokens", "cost_usd", "latency_s",
                                                                                       "trace_id")}, default=str)))


def save_state_snapshot(thread_id: str, out: dict) -> None:
    """Store the latest summary for the UI (job detail / studio) without re-reading checkpoints."""
    db.x("UPDATE jobs SET summary=%s, status=%s, fit_score=%s, risk_score=%s, action=%s, price=%s, updated_at=now() WHERE thread_id=%s",
         (json.dumps({k: out.get(k) for k in ("decision", "fit", "risk", "price", "job_spec", "draft", "drafts", "critiques", "compliance",
                                                "preview", "submission", "status", "status_reason", "trace", "errors", "evidence", "trace_id",
                                                "tokens", "cost_usd", "latency_s", "pending_approval")}, default=str),
          out.get("status"), (out.get("fit") or {}).get("fit_score"), (out.get("risk") or {}).get("risk_score"),
          (out.get("decision") or {}).get("action"), (out.get("price") or {}).get("amount"), thread_id))


# ------------------------------------------------------------------ tasks
async def analyse_job(ctx, user_id: str, job_id: str, force: bool = False) -> dict:
    from agent.runner import run_bid
    user = user_row(user_id)
    row = db.one("SELECT * FROM jobs WHERE user_id=%s AND job_id=%s", (user_id, job_id))
    thread_id = (row or {}).get("thread_id") if row and not force else None
    thread_id = thread_id or f"bid-{user_id[-6:]}-{job_id}-{int(time.time()) % 100000}"
    if row is None:
        db.x("INSERT INTO jobs(user_id, job_id, title, data, status, thread_id) VALUES (%s,%s,%s,%s,'analysing',%s) ON CONFLICT DO NOTHING",
             (user_id, job_id, job_id, json.dumps({"job_id": job_id}), thread_id))
    else:
        db.x("UPDATE jobs SET thread_id=%s, status='analysing', updated_at=now() WHERE user_id=%s AND job_id=%s", (thread_id, user_id, job_id))
    db.x("INSERT INTO runs(thread_id, user_id, kind, job_id, status) VALUES (%s,%s,'bid',%s,'running') ON CONFLICT (thread_id) DO NOTHING",
         (thread_id, user_id, job_id))
    out = await run_bid(user, {"job_id": job_id}, thread_id=thread_id, emit=emitter(thread_id, user_id))
    db.x("UPDATE jobs SET title=COALESCE(%s, title), data=%s WHERE user_id=%s AND job_id=%s",
         ((out.get("job_spec") or {}).get("summary") and None, json.dumps({"job_id": job_id}), user_id, job_id))
    save_state_snapshot(thread_id, out)
    record_run(thread_id, user_id, "bid", job_id, out)
    return {"thread_id": thread_id, "status": out["status"]}


async def resume_thread(ctx, user_id: str, thread_id: str, decision: dict, kind: str = "bid") -> dict:
    from agent.runner import resume_bid, resume_conversation
    user = user_row(user_id)
    fn = resume_bid if kind == "bid" else resume_conversation
    out = await fn(user, thread_id, decision, emit=emitter(thread_id, user_id))
    if kind == "bid":
        save_state_snapshot(thread_id, out)
        if out.get("submission") and out["status"] in ("submitted", "awaiting_confirmation_on_upwork"):
            s = out["submission"]
            job = db.one("SELECT job_id, title FROM jobs WHERE thread_id=%s", (thread_id,)) or {}
            db.x("""INSERT INTO pipeline(user_id, proposal_id, job_id, title, stage, connects_spent, bid_amount, thread_id, data)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (user_id, proposal_id) DO UPDATE SET stage=EXCLUDED.stage, updated_at=now()""",
                 (user_id, s["proposal_id"], job.get("job_id"), job.get("title"), s["status"], s.get("connects_spent", 0),
                  (out.get("price") or {}).get("amount"), thread_id, json.dumps({"category": (out.get("job_spec") or {}).get("category"),
                                                                                 "cited": (out.get("draft") or {}).get("evidence_ids", [])})))
    record_run(thread_id, user_id, kind, None, out)
    return {"thread_id": thread_id, "status": out["status"]}


async def converse(ctx, user_id: str, marketplace_thread_id: str) -> dict:
    from agent.runner import run_conversation
    user = user_row(user_id)
    p = db.one("SELECT * FROM pipeline WHERE user_id=%s AND marketplace_thread_id=%s", (user_id, marketplace_thread_id)) or {}
    jr = db.one("SELECT summary FROM jobs WHERE user_id=%s AND job_id=%s", (user_id, p.get("job_id"))) if p.get("job_id") else None
    job = {"title": p.get("title"), "job_id": p.get("job_id")}
    proposal = {"cover_letter": ((jr or {}).get("summary") or {}).get("draft", {}).get("cover_letter", ""), "bid_amount": p.get("bid_amount"),
                "bid_type": (((jr or {}).get("summary") or {}).get("price") or {}).get("bid_type")}
    thread_id = f"conv-{user_id[-6:]}-{marketplace_thread_id}-{int(time.time()) % 100000}"
    db.x("INSERT INTO runs(thread_id, user_id, kind, conversation_id, status) VALUES (%s,%s,'conversation',%s,'running') ON CONFLICT DO NOTHING",
         (thread_id, user_id, marketplace_thread_id))
    out = await run_conversation(user, marketplace_thread_id, job, proposal, thread_id=thread_id, emit=emitter(thread_id, user_id))
    db.x("""INSERT INTO conversations(user_id, marketplace_thread_id, proposal_id, job_id, graph_thread_id, state) VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (user_id, marketplace_thread_id) DO UPDATE SET graph_thread_id=EXCLUDED.graph_thread_id, state=EXCLUDED.state, updated_at=now()""",
         (user_id, marketplace_thread_id, p.get("proposal_id"), p.get("job_id"), thread_id, out.get("status")))
    record_run(thread_id, user_id, "conversation", p.get("job_id"), out, marketplace_thread_id)
    return {"thread_id": thread_id, "status": out["status"]}


async def scout(ctx, user_id: str, search_id: str | None = None) -> dict:
    """Poll saved searches through the marketplace port, dedupe reposts, queue analysis for new jobs."""
    user = user_row(user_id)
    port = await port_for(user)
    searches = db.q("SELECT * FROM saved_searches WHERE user_id=%s AND enabled" + (" AND search_id=%s" if search_id else ""),
                    (user_id, search_id) if search_id else (user_id,))
    new, dupes = [], 0
    for s in searches:
        res = await port.search_jobs(query=s["query"], category=s.get("category"), limit=25, since_minute=s.get("last_seen_minute"))
        maxm = s.get("last_seen_minute") or 0
        for j in res.get("jobs", []):
            maxm = max(maxm, j.get("posted_minute") or 0)
            if db.one("SELECT 1 FROM jobs WHERE user_id=%s AND job_id=%s", (user_id, j["job_id"])):
                continue
            k = dedup_key(j)
            orig = db.one("SELECT job_id FROM jobs WHERE user_id=%s AND dedup_key=%s AND duplicate_of IS NULL", (user_id, k))
            db.x("INSERT INTO jobs(user_id, job_id, title, data, dedup_key, duplicate_of, status) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                 (user_id, j["job_id"], j["title"], json.dumps(j), k, orig["job_id"] if orig else None, "duplicate" if orig else "queued"))
            if orig:
                dupes += 1
            else:
                new.append(j["job_id"])
        db.x("UPDATE saved_searches SET last_run_at=now(), last_seen_minute=%s WHERE search_id=%s", (maxm, s["search_id"]))
    for jid in new[: int(os.environ.get("SCOUT_MAX_PER_RUN", "6"))]:
        await enqueue("analyse_job", user_id, jid)
    return {"new": len(new), "duplicates": dupes}


async def sync_pipeline(ctx, user_id: str) -> dict:
    """Pull proposal statuses and new client messages; update the pipeline and outcome memory; queue reply drafts."""
    from agent.memory.outcomes import record_outcome
    user = user_row(user_id)
    port = await port_for(user)
    props = (await port.list_proposals()).get("proposals", [])
    changed = 0
    for p in props:
        if p.get("status") == "draft":
            continue
        row = db.one("SELECT * FROM pipeline WHERE user_id=%s AND proposal_id=%s", (user_id, p["proposal_id"]))
        if row and row["stage"] != p["status"]:
            db.x("UPDATE pipeline SET stage=%s, updated_at=now() WHERE user_id=%s AND proposal_id=%s", (p["status"], user_id, p["proposal_id"]))
            changed += 1
            data = row.get("data") or {}
            if p["status"] in ("replied", "interview", "hired", "lost"):
                record_outcome(user_id, data.get("category"), p["proposal_id"], p["status"], data.get("cited"))
    threads = (await port.list_threads()).get("threads", [])
    queued = 0
    for t in threads:
        db.x("UPDATE pipeline SET marketplace_thread_id=%s WHERE user_id=%s AND proposal_id=%s", (t["thread_id"], user_id, t.get("proposal_id")))
        last = t.get("last_message") or {}
        if last.get("sender") != "client":
            continue
        conv = db.one("SELECT * FROM conversations WHERE user_id=%s AND marketplace_thread_id=%s", (user_id, t["thread_id"]))
        if conv and conv.get("last_message_id") == last.get("message_id"):
            continue
        db.x("""INSERT INTO conversations(user_id, marketplace_thread_id, proposal_id, last_message_id, state) VALUES (%s,%s,%s,%s,'queued')
                ON CONFLICT (user_id, marketplace_thread_id) DO UPDATE SET last_message_id=EXCLUDED.last_message_id, state='queued'""",
             (user_id, t["thread_id"], t.get("proposal_id"), last.get("message_id")))
        await enqueue("converse", user_id, t["thread_id"])
        queued += 1
    return {"changed": changed, "replies_queued": queued}


async def tick(ctx) -> dict:
    """Cron: run due saved searches and pipeline sync for every user."""
    users = db.q("SELECT user_id FROM users WHERE onboarded")
    for u in users:
        due = db.q("SELECT search_id FROM saved_searches WHERE user_id=%s AND enabled AND (last_run_at IS NULL OR "
                   "last_run_at < now() - make_interval(mins => interval_minutes))", (u["user_id"],))
        if due:
            await enqueue("scout", u["user_id"])
        await enqueue("sync_pipeline", u["user_id"])
    return {"users": len(users)}


TASKS = {"analyse_job": analyse_job, "resume_thread": resume_thread, "converse": converse, "scout": scout,
         "sync_pipeline": sync_pipeline, "tick": tick}
_redis_pool = None
_inline_tasks: set = set()


async def enqueue(name: str, *args, **kw) -> str:
    """Queue a task on Redis (Arq). Without REDIS_URL (tests) the task runs as a background asyncio task."""
    global _redis_pool
    if os.environ.get("REDIS_URL"):
        from arq import create_pool
        from arq.connections import RedisSettings
        if _redis_pool is None:
            _redis_pool = await create_pool(RedisSettings.from_dsn(os.environ["REDIS_URL"]))
        job = await _redis_pool.enqueue_job(name, *args, **kw)
        return job.job_id if job else "duplicate"
    t = asyncio.create_task(TASKS[name]({}, *args, **kw))
    _inline_tasks.add(t)

    def _done(task):
        _inline_tasks.discard(task)
        if not task.cancelled() and task.exception():
            log.error("inline task %s failed: %r", name, task.exception())
    t.add_done_callback(_done)
    return f"inline-{id(t)}"


settings  # noqa: B018
