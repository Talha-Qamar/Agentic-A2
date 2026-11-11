"""Run viewer + live streaming (SSE) of node events, tool calls, tokens and cost."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from apps.api.auth.session import UserDep
from common import db

router = APIRouter(prefix="/api/runs", tags=["runs"])
public_router = APIRouter(prefix="/api/public", tags=["public"])


class PublicIn(BaseModel):
    public: bool


def _trace_payload(r: dict) -> dict:
    ev = db.q("SELECT id, ts, node, kind, payload FROM run_events WHERE user_id=%s AND thread_id=%s ORDER BY id", (r["user_id"], r["thread_id"]))
    job = db.one("SELECT summary FROM jobs WHERE user_id=%s AND thread_id=%s", (r["user_id"], r["thread_id"]))
    audit = db.q("SELECT ts, server, tool, arguments, status FROM audit_log WHERE trace_id=%s ORDER BY id", (r.get("trace_id") or "-",))
    from agent.tracing import phoenix_link
    return {"run": r, "events": ev, "summary": (job or {}).get("summary"), "audit": audit, "phoenix_url": phoenix_link(r.get("trace_id") or "")}


@public_router.get("/traces/{thread_id}")
def public_trace(thread_id: str):
    """Read-only trace page for runs their owner explicitly published (PII already masked at write time)."""
    r = db.one("SELECT * FROM runs WHERE thread_id=%s AND public", (thread_id,))
    if not r:
        raise HTTPException(404, "trace not found or not public")
    out = _trace_payload(r)
    out["run"] = {k: v for k, v in r.items() if k != "user_id"}
    out["phoenix_url"] = None
    return out


@router.get("")
def list_runs(user=UserDep, limit: int = 50):
    return db.q("SELECT thread_id, kind, job_id, status, status_reason, trace_id, tokens, cost_usd, latency_s, created_at, updated_at "
                "FROM runs WHERE user_id=%s ORDER BY created_at DESC LIMIT %s", (user["user_id"], min(limit, 200)))


@router.get("/{thread_id}")
def get_run(thread_id: str, user=UserDep):
    r = db.one("SELECT * FROM runs WHERE user_id=%s AND thread_id=%s", (user["user_id"], thread_id))
    if not r:
        raise HTTPException(404, "run not found")
    return _trace_payload(r)


@router.post("/{thread_id}/public")
def set_public(thread_id: str, body: PublicIn, user=UserDep):
    n = db.x("UPDATE runs SET public=%s WHERE user_id=%s AND thread_id=%s", (body.public, user["user_id"], thread_id))
    if not n:
        raise HTTPException(404, "run not found")
    return {"thread_id": thread_id, "public": body.public, "url": f"/t/{thread_id}" if body.public else None}


@router.get("/{thread_id}/stream")
async def stream(thread_id: str, request: Request, user=UserDep, since: int = 0):
    uid = user["user_id"]

    async def gen():
        last, idle = since, 0
        while not await request.is_disconnected():
            rows = db.q("SELECT id, ts, node, kind, payload FROM run_events WHERE user_id=%s AND thread_id=%s AND id>%s ORDER BY id LIMIT 200",
                        (uid, thread_id, last))
            for r in rows:
                last = r["id"]
                yield {"id": str(r["id"]), "event": r["kind"], "data": json.dumps({"node": r["node"], "payload": r["payload"], "ts": r["ts"].isoformat()})}
                if r["kind"] == "run_end":
                    idle = 10_000
            idle = idle + 1 if not rows else (idle if idle >= 10_000 else 0)
            if idle >= 10_000 and not rows:
                yield {"event": "done", "data": "{}"}
                idle = 0
            await asyncio.sleep(0.8)
    return EventSourceResponse(gen(), ping=15)
