"""Typed graph state (C2).

Three things are kept apart:
* State (this file): what one job/conversation thread needs right now; checkpointed by LangGraph.
* Execution trace: every node event, tool call, argument, result and LLM call -> `trace` field
  (append-only reducer), mirrored to the run_events table and OpenTelemetry. Never fed back as memory.
* Long-term memory: only promoted knowledge, written to the LangGraph store by agent/memory/promotion_rules.py.

Reducers are used wherever parallel branches write (analyst/risk/matcher fan-out).
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


def merge_dict(a: dict | None, b: dict | None) -> dict:
    out = dict(a or {})
    out.update(b or {})
    return out


def merge_evidence(a: list[dict] | None, b: list[dict] | None) -> list[dict]:
    """Union evidence by id, keeping the highest score."""
    by_id: dict[str, dict] = {e["evidence_id"]: e for e in (a or [])}
    for e in b or []:
        cur = by_id.get(e["evidence_id"])
        if cur is None or e.get("score", 0) > cur.get("score", 0):
            by_id[e["evidence_id"]] = e
    return sorted(by_id.values(), key=lambda e: -e.get("score", 0))


def add_int(a: int | None, b: int | None) -> int:
    return (a or 0) + (b or 0)


def last_value(a: Any, b: Any) -> Any:
    return b if b is not None else a


class BidState(TypedDict, total=False):
    # identity
    thread_id: str
    user_id: str
    persona: str
    trace_id: str
    # input (untrusted)
    job: dict
    job_clean_text: str
    # analyses (written by parallel branches)
    job_spec: dict
    risk: dict
    fit: dict
    evidence: Annotated[list[dict], merge_evidence]
    # decision and downstream
    decision: dict
    price: dict
    drafts: Annotated[list[dict], operator.add]
    critiques: Annotated[list[dict], operator.add]
    compliance: dict
    preview: dict
    approvals: Annotated[list[dict], operator.add]
    submission: dict
    outcome: dict
    # control
    revision: int
    status: str
    status_reason: str
    steps: Annotated[int, add_int]
    tokens: Annotated[int, add_int]
    cost_usd: Annotated[float, operator.add]
    errors: Annotated[list[dict], operator.add]
    trace: Annotated[list[dict], operator.add]
    regenerate_paragraph: int | None
    settings: dict


class ConversationState(TypedDict, total=False):
    thread_id: str
    user_id: str
    persona: str
    trace_id: str
    marketplace_thread_id: str
    job: dict
    proposal: dict
    messages: list[dict]
    last_client_message: dict
    intent: dict
    reply: dict
    compliance: dict
    preview: dict
    approvals: Annotated[list[dict], operator.add]
    sent: dict
    status: str
    status_reason: str
    steps: Annotated[int, add_int]
    tokens: Annotated[int, add_int]
    cost_usd: Annotated[float, operator.add]
    errors: Annotated[list[dict], operator.add]
    trace: Annotated[list[dict], operator.add]
