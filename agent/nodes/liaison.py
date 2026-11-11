"""Client Liaison nodes for the conversation graph: classify -> draft reply -> compliance -> preview -> approve -> send."""
from __future__ import annotations

import hashlib

from langgraph.graph import END
from langgraph.types import Command, interrupt

from agent.guardrails import detect_injection, quarantine, wrap_untrusted
from agent.handoffs import ApprovalDecision, IntentResult, ReplyDraft
from agent.llm import complete_json, load_prompt
from agent.nodes.compliance import check
from agent.nodes.runtime import Deps, node


@node("load_thread", retries=1)
async def load_thread(state: dict, deps: Deps) -> dict:
    r = await deps.call("liaison", "list_messages", {"thread_id": state["marketplace_thread_id"]})
    msgs = r.get("messages", [])
    last = next((m for m in reversed(msgs) if m.get("sender") == "client"), None)
    if not last:
        return {"messages": msgs, "status": "no_client_message"}
    return {"messages": msgs, "last_client_message": last, "status": "classifying"}


@node("intent", retries=1)
async def intent(state: dict, deps: Deps):
    if state.get("status") == "no_client_message":
        return Command(goto=END, update={})
    text = state["last_client_message"]["text"]
    inj = detect_injection(text)
    clean, removed = quarantine(text) if inj["detected"] else (text, [])
    history = "\n".join(f"{m['sender']}: {m['text'][:300]}" for m in state.get("messages", [])[-6:])
    res = await complete_json("intent", load_prompt("intent"), f"Recent thread:\n{wrap_untrusted(history, 'thread')}\n\nLatest client message:\n"
                              f"{wrap_untrusted(clean, 'client_message')}", IntentResult)
    res.injection_detected = res.injection_detected or inj["detected"]
    return {"intent": res.model_dump() | {"quarantined": removed, "clean_text": clean}, "status": "drafting_reply"}


@node("liaison", retries=1)
async def liaison(state: dict, deps: Deps) -> dict:
    it = state["intent"]
    evidence, slots = [], []
    if it["intent"] == "question":
        r = await deps.call("liaison", "search_evidence", {"requirement": it["clean_text"][:450], "k": 4}) if "search_evidence" in deps.tools_for("liaison") else {}
        evidence = r.get("items", []) if isinstance(r, dict) else []
    if it["intent"] == "interview_request":
        s = await deps.call("liaison", "free_slots", {"days": 5, "duration_min": 30, "max_slots": 3})
        slots = s.get("slots", [])
    floor = deps.profile.get("hourly_floor", 25)
    bid = (state.get("proposal") or {}).get("bid_amount")
    if bid and (state.get("proposal") or {}).get("bid_type") == "fixed":
        floor = round(bid * 0.8)
    sys = load_prompt("liaison").format(intent=it["intent"], floor=floor)
    ev = "\n".join(f"[{e['evidence_id']}] {e['text'][:500]}" for e in evidence) or "(none)"
    sl = "\n".join(f"- start: {s['start']} | label: {s['label']}" for s in slots) or "(none)"
    user = (f"Job: {(state.get('job') or {}).get('title', '')}\nOur proposal (excerpt): {(state.get('proposal') or {}).get('cover_letter', '')[:600]}\n"
            f"EVIDENCE:\n{ev}\nSLOTS:\n{sl}\n\nClient message:\n{wrap_untrusted(it['clean_text'], 'client_message')}")
    reply = await complete_json("liaison", sys, user, ReplyDraft, max_tokens=600)
    if it["intent"] == "interview_request" and slots and not reply.proposed_slots:
        reply.proposed_slots = [{"start": s["start"], "label": s["label"]} for s in slots[:2]]
    if reply.counter_offer is not None and reply.counter_offer < floor:
        reply.counter_offer = floor
        reply.notes.append(f"counter raised to floor {floor}")
    return {"reply": reply.model_dump(), "status": "compliance"}


@node("reply_compliance", retries=1)
async def reply_compliance(state: dict, deps: Deps):
    v = await check(state["reply"]["text"], {}, use_llm=False)
    if not v.allowed:
        return Command(goto=END, update={"compliance": v.model_dump(), "status": "blocked", "status_reason": v.blocked_reason})
    key = "msg-" + hashlib.sha256(f"{state['thread_id']}|{state['last_client_message'].get('message_id')}|{v.final_text}".encode()).hexdigest()[:24]
    dry = await deps.call("liaison", "send_message", {"thread_id": state["marketplace_thread_id"], "text": v.final_text,
                                                      "idempotency_key": key, "dry_run": True})
    return Command(goto="reply_approval", update={"compliance": v.model_dump(), "status": "awaiting_approval",
                                                  "preview": {"text": v.final_text, "idempotency_key": key, "dry_run": dry}})


@node("reply_approval", retries=0)
async def reply_approval(state: dict, deps: Deps):
    pv = state["preview"]
    raw = interrupt({"type": "message_approval", "thread_id": state["thread_id"], "marketplace_thread_id": state["marketplace_thread_id"],
                     "client_message": state["last_client_message"]["text"], "intent": state["intent"], "text": pv["text"],
                     "idempotency_key": pv["idempotency_key"], "proposed_slots": state["reply"].get("proposed_slots", [])})
    d = ApprovalDecision(**{k: raw.get(k) for k in ("action", "edited_text", "reason", "approver")})
    rec = d.model_dump()
    if d.action == "reject":
        return Command(goto=END, update={"approvals": [rec], "status": "rejected", "status_reason": d.reason or "rejected"})
    if d.action == "edit" and d.edited_text:
        return Command(goto="reply_compliance", update={"approvals": [rec], "reply": dict(state["reply"], text=d.edited_text)})
    rec["approval_token"] = raw.get("approval_token")
    return Command(goto="send", update={"approvals": [rec], "status": "sending"})


@node("send", retries=2)
async def send(state: dict, deps: Deps) -> dict:
    pv = state["preview"]
    r = await deps.call("liaison", "send_message", {"thread_id": state["marketplace_thread_id"], "text": pv["text"],
                                                    "idempotency_key": pv["idempotency_key"], "dry_run": False,
                                                    "approval_token": state["approvals"][-1].get("approval_token")})
    out = {"sent": r, "status": "sent"}
    slots = state["reply"].get("proposed_slots") or []
    if state["intent"]["intent"] == "interview_request" and slots and slots[0].get("start"):
        hold = await deps.call("liaison", "create_interview_hold", {
            "start": slots[0]["start"], "duration_min": 30, "title": f"Tentative: interview - {(state.get('job') or {}).get('title', '')[:60]}",
            "idempotency_key": "hold-" + pv["idempotency_key"][4:]})
        out["hold"] = hold
    return out
