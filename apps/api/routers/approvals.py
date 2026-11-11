"""Human approval: the ONLY place approval tokens are minted (R4)."""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.api.auth.session import UserDep
from common import db
from common.tokens import mint_approval
from worker.tasks import enqueue

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


class DecisionIn(BaseModel):
    action: str = Field(pattern="^(approve|edit|reject|regenerate)$")
    edited_text: str | None = Field(None, max_length=6000)
    reason: str | None = Field(None, max_length=500)
    paragraph: int | None = Field(None, ge=0, le=20)


@router.get("")
def pending(user=UserDep):
    return db.q("SELECT approval_id, thread_id, kind, payload, created_at FROM approvals WHERE user_id=%s AND status='pending' ORDER BY created_at DESC",
                (user["user_id"],))


@router.post("/{approval_id}")
async def decide(approval_id: str, body: DecisionIn, user=UserDep):
    a = db.one("SELECT * FROM approvals WHERE user_id=%s AND approval_id=%s", (user["user_id"], approval_id))
    if not a:
        raise HTTPException(404, "approval not found")
    if a["status"] != "pending":
        raise HTTPException(409, f"already {a['status']}")
    p = a["payload"]
    decision = {"action": body.action, "edited_text": body.edited_text, "reason": body.reason, "paragraph": body.paragraph,
                "approver": user["email"]}
    if body.action == "approve":
        if a["kind"] == "proposal_approval":
            decision["approval_token"] = mint_approval(user["user_id"], "submit_proposal",
                                                       {"proposal_id": p["proposal_id"], "idempotency_key": p["submit_key"]})
        else:
            decision["approval_token"] = mint_approval(user["user_id"], "send_message", {"thread_id": p["marketplace_thread_id"],
                                                       "idempotency_key": p["idempotency_key"], "text": p["text"]})
    db.x("UPDATE approvals SET status='decided', decision=%s, decided_at=now() WHERE approval_id=%s",
         (json.dumps({k: v for k, v in decision.items() if k != "approval_token"}), approval_id))
    kind = "bid" if a["kind"] == "proposal_approval" else "conversation"
    jid = await enqueue("resume_thread", user["user_id"], a["thread_id"], decision, kind)
    return {"queued": jid, "thread_id": a["thread_id"]}
