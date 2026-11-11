"""Run viewer + live streaming (SSE) of node events, tool calls, tokens and cost."""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from apps.api.auth.session import UserDep
from common import db

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("")
def list_runs(user=UserDep, limit: int = 50):
    return db.q("SELECT thread_id, kind, job_id, status, status_reason, trace_id, tokens, cost_usd, latency_s, created_at, updated_at "
                "FROM runs WHERE user_id=%s ORDER BY created_at DESC LIMIT %s", (user["user_id"], min(limit, 200)))


@router.get("/{thread_id}")
def get_run(thread_id: str, user=UserDep):
    r = db.one("SELECT * FROM runs WHERE user_id=%s AND thread_id=%s", (user["user_id"], thread_id))
    if not r:
        raise HTTPException(404, "run not found")
    ev = db.q("SELECT id, ts, node, kind, payload FROM run_events WHERE user_id=%s AND thread_id=%s ORDER BY id", (user["user_id"], thread_id))
    job = db.one("SELECT summary FROM jobs WHERE user_id=%s AND thread_id=%s", (user["user_id"], thread_id))
    from agent.tracing import phoenix_link
    return {"run": r, "events": ev, "summary": (job or {}).get("summary"), "phoenix_url": phoenix_link(r.get("trace_id") or "")}


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
