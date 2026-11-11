"""GigSim: a freelance-marketplace simulator (REST API).

Run:  uvicorn gigsim.app:app --port 8100
Auth: header ``X-GigSim-Key`` (seeded keys: gs-key-<persona>); admin: ``X-Admin-Key``.
Realism: per-key rate limits (429 + Retry-After), random 5xx, a fault switch, idempotent
writes, Connects accounting and versioned platform policies.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import threading
import time
import uuid
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from . import engine
from .policy import available_versions, connects_cost, current_policy, load_policy, policy_violations
from .store import Store

ADMIN_KEY = os.environ.get("GIGSIM_ADMIN_KEY", "gigsim-admin")
RATE_PER_MIN = int(os.environ.get("GIGSIM_RATE_LIMIT_PER_MIN", "120"))

store = Store()
_buckets: dict[str, deque] = defaultdict(deque)
_bucket_lock = threading.Lock()
_fault = {"down": False, "error_rate": float(os.environ.get("GIGSIM_ERROR_RATE", "0.02"))}
_err_rng = random.Random(7)


def j(row) -> dict:
    return json.loads(row["data"])


# ------------------------------------------------------------------ app + middleware
app = FastAPI(title="GigSim", version="1.0.0", description="Freelance marketplace simulator for GigBid")


@app.middleware("http")
async def realism(request: Request, call_next):
    path = request.url.path
    if path.endswith("/health") or "/admin/" in path or path.endswith("/openapi.json") or path.endswith("/docs"):
        return await call_next(request)
    if _fault["down"]:
        return JSONResponse({"error": "service_unavailable", "detail": "GigSim is down (fault injected)"}, status_code=503)
    key = request.headers.get("x-gigsim-key", "anon")
    now = time.time()
    with _bucket_lock:
        b = _buckets[key]
        while b and now - b[0] > 60:
            b.popleft()
        if len(b) >= RATE_PER_MIN:
            retry = max(1, int(60 - (now - b[0])) + 1)
            return JSONResponse({"error": "rate_limited", "retry_after": retry}, status_code=429,
                                headers={"Retry-After": str(retry)})
        b.append(now)
    if _fault["error_rate"] and _err_rng.random() < _fault["error_rate"]:
        return JSONResponse({"error": "internal", "detail": "transient upstream error"}, status_code=503)
    process_due_events()
    return await call_next(request)


@app.on_event("startup")
def _startup():
    if not store.seeded():
        store.seed()


def account(x_gigsim_key: str = Header(...)) -> dict:
    r = store.q("SELECT * FROM accounts WHERE api_key=?", (x_gigsim_key,))
    if not r:
        raise HTTPException(401, "invalid GigSim key")
    return dict(r[0])


def admin(x_admin_key: str = Header(...)) -> None:
    if x_admin_key != ADMIN_KEY:
        raise HTTPException(403, "admin key required")


# ------------------------------------------------------------------ events
def schedule(account_id: str, etype: str, ref_id: str, delay_min: float, payload: dict | None = None) -> None:
    store.x("INSERT INTO events(account_id,type,ref_id,due_sim,payload) VALUES(?,?,?,?,?)",
            (account_id, etype, ref_id, store.sim_minutes() + delay_min, json.dumps(payload or {})))


def process_due_events(until: float | None = None) -> int:
    now = until if until is not None else store.sim_minutes()
    due = store.q("SELECT * FROM events WHERE processed=0 AND due_sim<=? AND type LIKE 'pending_%' ORDER BY due_sim", (now,))
    for e in due:
        payload = json.loads(e["payload"])
        store.x("UPDATE events SET processed=1 WHERE event_id=?", (e["event_id"],))
        etype = e["type"].removeprefix("pending_")
        pid = e["ref_id"]
        if etype == "viewed":
            store.x("UPDATE proposals SET status='viewed' WHERE proposal_id=? AND status='submitted'", (pid,))
        elif etype == "replied":
            prop = store.q("SELECT * FROM proposals WHERE proposal_id=?", (pid,))[0]
            store.x("UPDATE proposals SET status='replied' WHERE proposal_id=?", (pid,))
            tid = "th-" + pid
            store.x("INSERT OR IGNORE INTO threads VALUES(?,?,?,?,?,?,?)",
                    (tid, prop["account_id"], pid, prop["job_id"], payload["client_id"], payload["intent"], now))
            store.x("INSERT INTO messages VALUES(?,?,?,?,?,?)",
                    ("m-" + uuid.uuid4().hex[:10], tid, "client", payload["text"], now, None))
        elif etype == "lost":
            store.x("UPDATE proposals SET status='lost' WHERE proposal_id=? AND status IN ('submitted','viewed')", (pid,))
        elif etype == "client_message":
            store.x("INSERT INTO messages VALUES(?,?,?,?,?,?)",
                    ("m-" + uuid.uuid4().hex[:10], payload["thread_id"], "client", payload["text"], now, None))
            if payload.get("status"):
                store.x("UPDATE proposals SET status=? WHERE proposal_id=?", (payload["status"], pid))
        # public event visible to the freelancer
        store.x("INSERT INTO events(account_id,type,ref_id,due_sim,processed,payload) VALUES(?,?,?,?,1,?)",
                (e["account_id"], etype, pid, now, e["payload"]))
    return len(due)


# ------------------------------------------------------------------ read endpoints
@app.get("/health")
def health():
    return {"ok": True, "sim_minutes": round(store.sim_minutes(), 1), "policy": current_policy(store)["version"],
            "down": _fault["down"]}


@app.get("/v1/policy")
def get_policy(acct: dict = Depends(account)):
    return current_policy(store)


@app.get("/v1/account")
def get_account(acct: dict = Depends(account)):
    pol = current_policy(store)
    since = store.sim_minutes() - 1440
    recent = store.q("SELECT COUNT(*) n FROM proposals WHERE account_id=? AND status!='draft' AND created_sim>=?",
                     (acct["account_id"], since))[0]["n"]
    return {"account_id": acct["account_id"], "persona": acct["persona"], "connects_balance": acct["connects"],
            "weekly_allowance": pol["connects"]["weekly_allowance"], "proposals_last_24h": recent,
            "daily_proposal_cap": pol["limits"]["daily_proposal_cap"]}


def visible_jobs(pool: str) -> list[dict]:
    if pool == "stream":
        rows = store.q("SELECT * FROM jobs WHERE pool='stream' AND release_minute<=? ORDER BY release_minute DESC",
                       (store.sim_minutes(),))
    else:
        rows = store.q("SELECT * FROM jobs WHERE pool=?", (pool,))
    out = []
    for r in rows:
        d = j(r)
        d["posted_minute"] = r["release_minute"]
        out.append(d)
    return out


@app.get("/v1/jobs")
def search_jobs(q: str = "", category: str | None = None, pool: str = Query("stream", pattern="^(stream|dev|historical)$"),
                persona: str | None = None, since_minute: float | None = None, limit: int = Query(20, le=100), offset: int = 0,
                acct: dict = Depends(account)):
    jobs = visible_jobs(pool)
    terms = [t for t in q.lower().split() if t]
    res = []
    for d in jobs:
        if category and d.get("category") != category:
            continue
        if persona and d.get("persona") and d["persona"] != persona:
            continue
        if since_minute is not None and d["posted_minute"] <= since_minute:
            continue
        hay = (d["title"] + " " + d["description"] + " " + " ".join(d.get("skills", []))).lower()
        if terms and not any(t in hay for t in terms):
            continue
        res.append({k: d[k] for k in ("job_id", "title", "category", "posted_minute") if k in d} |
                   {"budget_type": d.get("budget_type"), "budget_max": d.get("budget_max"), "skills": d.get("skills", [])[:8],
                    "snippet": d["description"][:240], "client_id": d.get("client", {}).get("client_id")})
    return {"total": len(res), "jobs": res[offset: offset + limit], "sim_minutes": round(store.sim_minutes(), 1)}


def get_job_row(job_id: str) -> dict:
    r = store.q("SELECT * FROM jobs WHERE job_id=?", (job_id,))
    if not r:
        raise HTTPException(404, f"job {job_id} not found")
    d = j(r[0])
    if r[0]["pool"] == "stream" and r[0]["release_minute"] > store.sim_minutes():
        raise HTTPException(404, f"job {job_id} not found")
    return d


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str, acct: dict = Depends(account)):
    d = get_job_row(job_id)
    pol = current_policy(store)
    d["connects_cost"] = connects_cost(pol, d)
    d["proposals_count"] = store.q("SELECT COUNT(*) n FROM proposals WHERE job_id=? AND status!='draft'", (job_id,))[0]["n"]
    return d


@app.get("/v1/clients/{client_id}")
def get_client(client_id: str, acct: dict = Depends(account)):
    r = store.q("SELECT * FROM clients WHERE client_id=?", (client_id,))
    if not r:
        raise HTTPException(404, "client not found")
    c = j(r[0])
    c.pop("hidden_preferences", None)
    return c


@app.get("/v1/market/stats")
def market_stats(category: str | None = None, acct: dict = Depends(account)):
    from pathlib import Path
    s = json.loads((Path(__file__).parent / "seed_data" / "market_stats.json").read_text())
    if category:
        return {"category": category, "hourly": s["hourly"].get(category, s["hourly_all"]),
                "fixed": s["fixed"].get(category, s["fixed_all"]), "source": s["source"],
                "fallback": category not in s["hourly"]}
    return {"hourly_all": s["hourly_all"], "fixed_all": s["fixed_all"], "categories": sorted(s["hourly"]), "source": s["source"]}


# ------------------------------------------------------------------ proposals
class DraftIn(BaseModel):
    job_id: str
    cover_letter: str = Field(min_length=1, max_length=8000)
    bid_amount: float = Field(gt=0, le=100000)
    bid_type: str = Field("fixed", pattern="^(fixed|hourly)$")
    screening_answers: list[str] = []
    idempotency_key: str = Field(min_length=8, max_length=128)


class SubmitIn(BaseModel):
    idempotency_key: str = Field(min_length=8, max_length=128)
    dry_run: bool = False


def payload_hash(d: dict) -> str:
    return hashlib.sha256(json.dumps(d, sort_keys=True).encode()).hexdigest()


def prop_out(r) -> dict:
    d = j(r)
    d.update(proposal_id=r["proposal_id"], status=r["status"], connects_spent=r["connects_spent"], job_id=r["job_id"])
    return d


@app.post("/v1/proposals/drafts")
def create_draft(body: DraftIn, acct: dict = Depends(account)):
    get_job_row(body.job_id)
    data = body.model_dump()
    h = payload_hash(data | {"op": "draft"})
    ex = store.q("SELECT * FROM proposals WHERE account_id=? AND idempotency_key=?", (acct["account_id"], body.idempotency_key))
    if ex:
        if ex[0]["payload_hash"] != h:
            raise HTTPException(409, "idempotency key reused with a different payload")
        return prop_out(ex[0]) | {"idempotent_replay": True}
    pid = "pr-" + uuid.uuid4().hex[:12]
    store.x("INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?,?)",
            (pid, acct["account_id"], body.job_id, "draft", body.idempotency_key, h, 0, store.sim_minutes(), json.dumps(data)))
    return prop_out(store.q("SELECT * FROM proposals WHERE proposal_id=?", (pid,))[0])


def _submit(acct: dict, pid: str, body: SubmitIn) -> dict:
    r = store.q("SELECT * FROM proposals WHERE proposal_id=? AND account_id=?", (pid, acct["account_id"]))
    if not r:
        raise HTTPException(404, "proposal not found")
    prop = dict(r[0])
    data = json.loads(prop["data"])
    job = get_job_row(prop["job_id"])
    pol = current_policy(store)
    cost = connects_cost(pol, job)
    violations = policy_violations(pol, data["cover_letter"])
    # exactly-once: a submit key that was already used returns the original result
    done = store.q("SELECT * FROM events WHERE account_id=? AND type='submit_key' AND ref_id=?",
                   (acct["account_id"], body.idempotency_key))
    if done and not body.dry_run:
        rec = json.loads(done[0]["payload"])
        if rec["proposal_id"] != pid:
            raise HTTPException(409, "idempotency key already used for another proposal")
        return prop_out(store.q("SELECT * FROM proposals WHERE proposal_id=?", (pid,))[0]) | {"idempotent_replay": True}
    acc = store.q("SELECT connects FROM accounts WHERE account_id=?", (acct["account_id"],))[0]["connects"]
    cap = pol["limits"]["daily_proposal_cap"]
    recent = store.q("SELECT COUNT(*) n FROM proposals WHERE account_id=? AND status!='draft' AND created_sim>=?",
                     (acct["account_id"], store.sim_minutes() - 1440))[0]["n"]
    preview = {"dry_run": True, "would_send": {"job_id": job["job_id"], "job_title": job["title"],
               "cover_letter": data["cover_letter"], "bid_amount": data["bid_amount"], "bid_type": data["bid_type"],
               "screening_answers": data.get("screening_answers", [])},
               "connects_cost": cost, "connects_balance": acc, "balance_after": acc - cost,
               "policy_version": pol["version"], "policy_violations": violations,
               "daily_cap": cap, "proposals_last_24h": recent,
               "would_be_accepted": not violations and acc >= cost and (cap is None or recent < cap)}
    if body.dry_run:
        return preview
    if prop["status"] != "draft":
        raise HTTPException(409, f"proposal already {prop['status']}")
    if violations:
        raise HTTPException(422, {"error": "policy_violation", "rules": violations, "policy_version": pol["version"]})
    if acc < cost:
        raise HTTPException(402, {"error": "insufficient_connects", "balance": acc, "cost": cost})
    if cap is not None and recent >= cap:
        raise HTTPException(429, {"error": "daily_proposal_cap", "cap": cap})
    store.x("UPDATE accounts SET connects=connects-? WHERE account_id=?", (cost, acct["account_id"]))
    store.x("UPDATE proposals SET status='submitted', connects_spent=?, created_sim=? WHERE proposal_id=?",
            (cost, store.sim_minutes(), pid))
    store.x("INSERT INTO events(account_id,type,ref_id,due_sim,processed,payload) VALUES(?,?,?,?,1,?)",
            (acct["account_id"], "submit_key", body.idempotency_key, store.sim_minutes(), json.dumps({"proposal_id": pid})))
    # client reaction
    crow = store.q("SELECT data FROM clients WHERE client_id=?", (job["client"]["client_id"],))
    client = json.loads(crow[0]["data"]) if crow else job["client"]
    decision = engine.decide(job, client, {**data, "proposal_id": pid})
    rng = engine._rng("delay", pid)
    schedule(acct["account_id"], "pending_viewed", pid, rng.uniform(5, 60))
    if decision["replied"]:
        intent, text = engine.first_client_message(job, client, decision, {**data, "proposal_id": pid})
        schedule(acct["account_id"], "pending_replied", pid, rng.uniform(60, 240),
                 {"client_id": client["client_id"], "intent": intent, "text": text, "decision": decision})
    else:
        schedule(acct["account_id"], "pending_lost", pid, rng.uniform(1440, 2880), {"decision": decision})
    out = prop_out(store.q("SELECT * FROM proposals WHERE proposal_id=?", (pid,))[0])
    store.x("UPDATE proposals SET data=? WHERE proposal_id=?", (json.dumps(data | {"_decision": decision}), pid))
    return out


@app.post("/v1/proposals/{proposal_id}/submit")
def submit(proposal_id: str, body: SubmitIn, acct: dict = Depends(account)):
    return _submit(acct, proposal_id, body)


@app.get("/v1/proposals")
def list_proposals(status: str | None = None, acct: dict = Depends(account)):
    rows = store.q("SELECT * FROM proposals WHERE account_id=? ORDER BY created_sim DESC", (acct["account_id"],))
    out = []
    for r in rows:
        if status and r["status"] != status:
            continue
        d = prop_out(r)
        d.pop("_decision", None)
        out.append(d)
    return {"proposals": out}


@app.get("/v1/proposals/{proposal_id}")
def get_proposal(proposal_id: str, acct: dict = Depends(account)):
    r = store.q("SELECT * FROM proposals WHERE proposal_id=? AND account_id=?", (proposal_id, acct["account_id"]))
    if not r:
        raise HTTPException(404, "proposal not found")
    d = prop_out(r[0])
    d.pop("_decision", None)
    return d


# ------------------------------------------------------------------ messages
class MessageIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    idempotency_key: str = Field(min_length=8, max_length=128)
    dry_run: bool = False


@app.get("/v1/threads")
def list_threads(acct: dict = Depends(account)):
    rows = store.q("SELECT * FROM threads WHERE account_id=? ORDER BY created_sim DESC", (acct["account_id"],))
    out = []
    for t in rows:
        last = store.q("SELECT * FROM messages WHERE thread_id=? ORDER BY created_sim DESC LIMIT 1", (t["thread_id"],))
        out.append(dict(t) | {"last_message": dict(last[0]) if last else None})
    return {"threads": out}


@app.get("/v1/threads/{thread_id}/messages")
def list_messages(thread_id: str, acct: dict = Depends(account)):
    t = store.q("SELECT * FROM threads WHERE thread_id=? AND account_id=?", (thread_id, acct["account_id"]))
    if not t:
        raise HTTPException(404, "thread not found")
    msgs = store.q("SELECT * FROM messages WHERE thread_id=? ORDER BY created_sim", (thread_id,))
    return {"thread": dict(t[0]), "messages": [dict(m) for m in msgs]}


@app.post("/v1/threads/{thread_id}/messages")
def send_message(thread_id: str, body: MessageIn, acct: dict = Depends(account)):
    t = store.q("SELECT * FROM threads WHERE thread_id=? AND account_id=?", (thread_id, acct["account_id"]))
    if not t:
        raise HTTPException(404, "thread not found")
    t = dict(t[0])
    pol = current_policy(store)
    viol = [v for v in policy_violations(pol, body.text + " " * 300) if v in ("no_off_platform",)]
    if body.dry_run:
        return {"dry_run": True, "would_send": {"thread_id": thread_id, "text": body.text}, "policy_violations": viol,
                "connects_cost": 0}
    ex = store.q("SELECT * FROM messages WHERE thread_id=? AND idempotency_key=?", (thread_id, body.idempotency_key))
    if ex:
        return dict(ex[0]) | {"idempotent_replay": True}
    if viol:
        raise HTTPException(422, {"error": "policy_violation", "rules": viol})
    mid = "m-" + uuid.uuid4().hex[:10]
    store.x("INSERT INTO messages VALUES(?,?,?,?,?,?)", (mid, thread_id, "freelancer", body.text, store.sim_minutes(),
                                                        body.idempotency_key))
    state, reply, ev = engine.client_followup(t["state"], body.text, thread_id + str(len(body.text)))
    store.x("UPDATE threads SET state=? WHERE thread_id=?", (state, thread_id))
    status = {"interview_scheduled": "interview", "hired": "hired", "lost": "lost"}.get(state)
    if reply:
        schedule(acct["account_id"], "pending_client_message", t["proposal_id"], engine._rng("d", mid).uniform(20, 120),
                 {"thread_id": thread_id, "text": reply, "status": status, "event": ev})
    elif status:
        store.x("UPDATE proposals SET status=? WHERE proposal_id=?", (status, t["proposal_id"]))
    return dict(store.q("SELECT * FROM messages WHERE message_id=?", (mid,))[0])


@app.get("/v1/events")
def events(since_id: int = 0, acct: dict = Depends(account)):
    rows = store.q("SELECT event_id,type,ref_id,due_sim FROM events WHERE account_id=? AND processed=1 AND event_id>? "
                   "AND type NOT LIKE 'pending_%' AND type!='submit_key' ORDER BY event_id LIMIT 200",
                   (acct["account_id"], since_id))
    return {"events": [dict(r) for r in rows]}


# ------------------------------------------------------------------ admin
class AdvanceIn(BaseModel):
    minutes: float = Field(gt=0, le=100000)


@app.post("/v1/admin/seed", dependencies=[Depends(admin)])
def admin_seed(force: bool = True):
    return store.seed(force=force)


@app.post("/v1/admin/advance", dependencies=[Depends(admin)])
def admin_advance(body: AdvanceIn):
    now = store.advance(body.minutes)
    return {"sim_minutes": now, "processed": process_due_events()}


@app.post("/v1/admin/flush", dependencies=[Depends(admin)])
def admin_flush():
    """Process every pending event now (used by evaluations to read outcomes quickly)."""
    last = store.q("SELECT MAX(due_sim) m FROM events WHERE processed=0")[0]["m"]
    total = 0
    while last is not None:
        total += process_due_events(until=last + 1)
        last = store.q("SELECT MAX(due_sim) m FROM events WHERE processed=0 AND type LIKE 'pending_%'")[0]["m"]
    return {"processed": total}


class PolicyIn(BaseModel):
    version: str


@app.post("/v1/admin/policy", dependencies=[Depends(admin)])
def admin_policy(body: PolicyIn):
    if body.version not in available_versions():
        raise HTTPException(404, f"unknown policy {body.version}; have {available_versions()}")
    store.set_meta("policy_version", body.version)
    return load_policy(body.version)


class FaultIn(BaseModel):
    down: bool | None = None
    error_rate: float | None = Field(None, ge=0, le=1)


@app.post("/v1/admin/fault", dependencies=[Depends(admin)])
def admin_fault(body: FaultIn):
    if body.down is not None:
        _fault["down"] = body.down
    if body.error_rate is not None:
        _fault["error_rate"] = body.error_rate
    return dict(_fault)


class AccountIn(BaseModel):
    persona: str = Field(pattern="^(ai_ml_engineer|fullstack_web_dev|data_analyst)$")
    api_key: str | None = Field(None, pattern=r"^gs-key-[\w-]{4,40}$", description="re-provision an existing key (after a reset)")
    account_id: str | None = Field(None, max_length=40)


@app.post("/v1/admin/accounts", dependencies=[Depends(admin)])
def admin_account(body: AccountIn):
    key = body.api_key or "gs-key-" + uuid.uuid4().hex[:16]
    return store.create_account(body.persona, api_key=key, account_id=body.account_id or "acct-" + uuid.uuid4().hex[:8])


@app.get("/v1/admin/proposals/{proposal_id}/decision", dependencies=[Depends(admin)])
def admin_decision(proposal_id: str):
    r = store.q("SELECT * FROM proposals WHERE proposal_id=?", (proposal_id,))
    if not r:
        raise HTTPException(404)
    return {"status": r[0]["status"], "decision": json.loads(r[0]["data"]).get("_decision")}
