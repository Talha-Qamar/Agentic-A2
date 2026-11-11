"""Run / resume graph threads. Shared by the worker, the evaluation harness and the tests."""
from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Callable

from langgraph.types import Command

from agent import settings
from agent.mcp_client import load_tools
from agent.nodes.runtime import Deps
from agent.tracing import metering, new_trace_id, trace_id_var
from common.tokens import mint_mcp_token

PERSONA_DIR = settings.ROOT / "data" / "personas"


def profile_for(persona: str, overrides: dict | None = None) -> dict:
    p = PERSONA_DIR / persona / "profile.json"
    prof = json.loads(p.read_text()) if p.exists() else {"hourly_floor": 25, "target_rate": 40}
    return {**prof, **(overrides or {})}


@asynccontextmanager
async def checkpointer_ctx():
    """Postgres checkpointer when DATABASE_URL is set (durable), else in-memory (tests)."""
    if os.environ.get("DATABASE_URL") and os.environ.get("GIGBID_CHECKPOINTER", "postgres") == "postgres":
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        async with AsyncPostgresSaver.from_conn_string(os.environ["DATABASE_URL"]) as cp:
            await cp.setup()
            yield cp
    else:
        yield _MEMORY_SAVER


from langgraph.checkpoint.memory import InMemorySaver  # noqa: E402

_MEMORY_SAVER = InMemorySaver()


async def make_deps(user: dict, emit: Callable[[str, str, dict], None] | None = None, defences: dict | None = None,
                    trace_id: str | None = None) -> Deps:
    persona = user.get("persona", "ai_ml_engineer")
    token = mint_mcp_token(user["user_id"], persona if not user.get("own_portfolio") else f"user:{user['user_id']}",
                           user.get("gigsim_key"), user.get("marketplace_mode", "gigsim"))
    tools = await load_tools(user["user_id"] if not user.get("portfolio_user") else user["portfolio_user"], token, trace_id=trace_id)
    style, outcomes = [], []
    try:
        from agent.memory.outcomes import load_outcome_insights
        from agent.memory.style import load_style_rules
        style = load_style_rules(user["user_id"])
        outcomes = load_outcome_insights(user["user_id"])
    except Exception:  # noqa: BLE001
        pass
    return Deps(user_id=user["user_id"], persona=persona, profile=profile_for(persona, user.get("settings")), tools=tools,
                emit=emit or (lambda n, k, p: None), defences=defences or {"delimit": True, "detect": True, "verify": True},
                style_rules=style, outcome_insights=outcomes)


def _interrupt_payload(snapshot) -> dict | None:
    for t in snapshot.tasks or []:
        for itr in getattr(t, "interrupts", []) or []:
            return itr.value
    return None


async def run_bid(user: dict, job: dict, thread_id: str | None = None, emit=None, defences: dict | None = None,
                  checkpointer=None) -> dict:
    """Run a bid thread until it ends or pauses at the approval interrupt. Returns a summary dict."""
    from agent.graphs.bid_graph import build_bid_graph
    thread_id = thread_id or f"bid-{uuid.uuid4().hex[:12]}"
    trace_id = new_trace_id()
    trace_id_var.set(trace_id)
    t0 = time.perf_counter()
    deps = await make_deps(user, emit, defences, trace_id)
    cfg = {"configurable": {"thread_id": thread_id, "deps": deps}, "recursion_limit": 60}
    init = {"thread_id": thread_id, "user_id": user["user_id"], "persona": deps.persona, "trace_id": trace_id, "job": job, "status": "queued"}

    async def go(cp):
        graph = build_bid_graph(checkpointer=cp)
        with metering():
            async for _ in graph.astream(init, cfg, stream_mode="updates"):
                pass
        return await graph.aget_state(cfg)

    if checkpointer is not None:
        snap = await go(checkpointer)
    else:
        async with checkpointer_ctx() as cp:
            snap = await go(cp)
    return summarize(thread_id, trace_id, snap, time.perf_counter() - t0)


async def resume_bid(user: dict, thread_id: str, decision: dict, emit=None, checkpointer=None) -> dict:
    from agent.graphs.bid_graph import build_bid_graph
    t0 = time.perf_counter()

    async def go(cp):
        graph = build_bid_graph(checkpointer=cp)
        cfg0 = {"configurable": {"thread_id": thread_id}}
        prev = await graph.aget_state(cfg0)
        tid = prev.values.get("trace_id") or new_trace_id()
        trace_id_var.set(tid)
        deps = await make_deps(user, emit, None, tid)
        cfg = {"configurable": {"thread_id": thread_id, "deps": deps}, "recursion_limit": 60}
        async for _ in graph.astream(Command(resume=decision), cfg, stream_mode="updates"):
            pass
        return await graph.aget_state(cfg), tid

    if checkpointer is not None:
        snap, tid = await go(checkpointer)
    else:
        async with checkpointer_ctx() as cp:
            snap, tid = await go(cp)
    return summarize(thread_id, tid, snap, time.perf_counter() - t0)


def summarize(thread_id: str, trace_id: str, snap, elapsed: float) -> dict:
    v = snap.values
    pending = _interrupt_payload(snap)
    draft = (v.get("drafts") or [{}])[-1]
    return {"thread_id": thread_id, "trace_id": trace_id, "status": v.get("status"), "status_reason": v.get("status_reason"),
            "decision": v.get("decision"), "fit": v.get("fit"), "risk": v.get("risk"), "price": v.get("price"),
            "job_spec": v.get("job_spec"), "draft": draft, "drafts": v.get("drafts", []), "critiques": v.get("critiques", []),
            "compliance": v.get("compliance"), "preview": v.get("preview"), "submission": v.get("submission"),
            "pending_approval": pending, "steps": v.get("steps", 0), "tokens": v.get("tokens", 0), "cost_usd": round(v.get("cost_usd", 0.0), 6),
            "latency_s": round(elapsed, 3), "trace": v.get("trace", []), "errors": v.get("errors", []), "evidence": v.get("evidence", [])}


def approval_token_for(user_id: str, pending: dict) -> str:
    from common.tokens import mint_approval
    return mint_approval(user_id, "submit_proposal", {"proposal_id": pending["proposal_id"], "idempotency_key": pending["submit_key"]})


Any  # noqa: B018


async def run_conversation(user: dict, marketplace_thread_id: str, job: dict | None = None, proposal: dict | None = None,
                           thread_id: str | None = None, emit=None, checkpointer=None) -> dict:
    from agent.graphs.conversation_graph import build_conversation_graph
    thread_id = thread_id or f"conv-{uuid.uuid4().hex[:12]}"
    trace_id = new_trace_id()
    trace_id_var.set(trace_id)
    t0 = time.perf_counter()
    deps = await make_deps(user, emit, None, trace_id)
    cfg = {"configurable": {"thread_id": thread_id, "deps": deps}, "recursion_limit": 40}
    init = {"thread_id": thread_id, "user_id": user["user_id"], "persona": deps.persona, "trace_id": trace_id,
            "marketplace_thread_id": marketplace_thread_id, "job": job or {}, "proposal": proposal or {}, "status": "queued"}

    async def go(cp):
        g = build_conversation_graph(checkpointer=cp)
        async for _ in g.astream(init, cfg, stream_mode="updates"):
            pass
        return await g.aget_state(cfg)
    if checkpointer is not None:
        snap = await go(checkpointer)
    else:
        async with checkpointer_ctx() as cp:
            snap = await go(cp)
    return summarize_conv(thread_id, trace_id, snap, time.perf_counter() - t0)


async def resume_conversation(user: dict, thread_id: str, decision: dict, emit=None, checkpointer=None) -> dict:
    from agent.graphs.conversation_graph import build_conversation_graph
    t0 = time.perf_counter()

    async def go(cp):
        g = build_conversation_graph(checkpointer=cp)
        prev = await g.aget_state({"configurable": {"thread_id": thread_id}})
        tid = prev.values.get("trace_id") or new_trace_id()
        trace_id_var.set(tid)
        deps = await make_deps(user, emit, None, tid)
        cfg = {"configurable": {"thread_id": thread_id, "deps": deps}, "recursion_limit": 40}
        async for _ in g.astream(Command(resume=decision), cfg, stream_mode="updates"):
            pass
        return await g.aget_state(cfg), tid
    if checkpointer is not None:
        snap, tid = await go(checkpointer)
    else:
        async with checkpointer_ctx() as cp:
            snap, tid = await go(cp)
    return summarize_conv(thread_id, tid, snap, time.perf_counter() - t0)


def summarize_conv(thread_id: str, trace_id: str, snap, elapsed: float) -> dict:
    v = snap.values
    return {"thread_id": thread_id, "trace_id": trace_id, "status": v.get("status"), "status_reason": v.get("status_reason"),
            "intent": v.get("intent"), "reply": v.get("reply"), "preview": v.get("preview"), "sent": v.get("sent"),
            "pending_approval": _interrupt_payload(snap), "steps": v.get("steps", 0), "tokens": v.get("tokens", 0),
            "cost_usd": round(v.get("cost_usd", 0.0), 6), "latency_s": round(elapsed, 3), "trace": v.get("trace", []),
            "errors": v.get("errors", []), "marketplace_thread_id": v.get("marketplace_thread_id")}


def message_token_for(user_id: str, pending: dict) -> str:
    from common.tokens import mint_approval
    return mint_approval(user_id, "send_message", {"thread_id": pending["marketplace_thread_id"],
                                                   "idempotency_key": pending["idempotency_key"], "text": pending["text"]})
