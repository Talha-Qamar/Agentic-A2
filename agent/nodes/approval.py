"""Preview -> human approval (LangGraph interrupt) -> exactly-once submit.

* preview: saves a marketplace DRAFT and asks the marketplace for a dry run of the submit, so the human sees exactly
  what would be sent and how many Connects it costs;
* approval: `interrupt()` pauses the thread (checkpointed in Postgres, survives restarts). Resume values:
  approve (with an approval token minted by the API), edit (text -> back through compliance + preview), reject (reason);
* submit: real submit with the SAME idempotency key as the preview; a crash/replay never submits twice.
"""
from __future__ import annotations

import hashlib

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command, interrupt

from agent.handoffs import ApprovalDecision, SubmissionResult
from agent.nodes.compliance import check
from agent.nodes.runtime import Deps, node


def keys(thread_id: str, version: int, text: str) -> tuple[str, str]:
    h = hashlib.sha256(f"{thread_id}|{version}|{text}".encode()).hexdigest()[:24]
    return f"draft-{h}", f"submit-{h}"


@node("preview", retries=1)
async def preview(state: dict, deps: Deps) -> dict:
    draft, price, comp = state["drafts"][-1], state["price"], state["compliance"]
    text = comp["final_text"]
    dkey, skey = keys(state["thread_id"], draft["version"], text)
    created = await deps.call("submitter", "create_proposal_draft", {
        "job_id": state["job"]["job_id"], "cover_letter": text, "bid_amount": price["amount"], "bid_type": price["bid_type"],
        "screening_answers": [a["answer"] for a in draft.get("screening_answers", [])], "idempotency_key": dkey})
    pid = created["proposal_id"]
    dry = await deps.call("submitter", "submit_proposal", {"proposal_id": pid, "idempotency_key": skey, "dry_run": True})
    pv = {"proposal_id": pid, "submit_key": skey, "draft_key": dkey, "cover_letter": text, "dry_run": dry,
          "connects_cost": dry.get("connects_cost"), "balance_after": dry.get("balance_after"),
          "platform_violations": dry.get("policy_violations", []), "would_be_accepted": dry.get("would_be_accepted")}
    status = "awaiting_approval" if dry.get("would_be_accepted", True) is not False else "needs_attention"
    reason = None if status == "awaiting_approval" else f"marketplace would reject: {dry.get('policy_violations')}"
    return {"preview": pv, "status": status, "status_reason": reason}


@node("approval", retries=0)
async def approval(state: dict, deps: Deps):
    if state.get("status") == "needs_attention":
        return Command(goto=END, update={})
    pv = state["preview"]
    payload = {"type": "proposal_approval", "thread_id": state["thread_id"], "job_id": state["job"]["job_id"],
               "job_title": state["job"]["title"], "proposal_id": pv["proposal_id"], "submit_key": pv["submit_key"],
               "cover_letter": pv["cover_letter"], "bid": state["price"], "connects_cost": pv["connects_cost"],
               "balance_after": pv["balance_after"], "fit": state["fit"].get("fit_score"), "risk": state["risk"].get("risk_score"),
               "claims": state["drafts"][-1].get("claims", []), "compliance": state["compliance"]}
    raw = interrupt(payload)
    d = ApprovalDecision(**{k: raw.get(k) for k in ("action", "edited_text", "reason", "approver")})
    rec = {**d.model_dump(), "proposal_id": pv["proposal_id"], "version": state["drafts"][-1]["version"]}
    if d.action == "reject":
        return Command(goto=END, update={"approvals": [rec], "status": "rejected", "status_reason": d.reason or "rejected by user"})
    if d.action == "edit" and d.edited_text and d.edited_text.strip() != pv["cover_letter"].strip():
        try:
            from agent.memory.style import record_edit
            record_edit(deps.user_id, state["thread_id"], pv["cover_letter"], d.edited_text)
        except Exception as e:  # noqa: BLE001
            deps.emit("approval", "memory_error", {"error": str(e)[:200]})
        v = await check(d.edited_text, (state.get("settings") or {}).get("policy") or {}, use_llm=False)
        new_draft = dict(state["drafts"][-1], version=state["drafts"][-1]["version"] + 1, cover_letter=d.edited_text, edited_by_human=True)
        if not v.allowed:
            return Command(goto=END, update={"approvals": [rec], "drafts": [new_draft], "compliance": v.model_dump(),
                                             "status": "blocked", "status_reason": "edited text: " + (v.blocked_reason or "")})
        return Command(goto="preview", update={"approvals": [rec], "drafts": [new_draft], "compliance": v.model_dump(),
                                               "status": "previewing"})
    rec["approval_token"] = raw.get("approval_token")
    return Command(goto="submit", update={"approvals": [rec], "status": "submitting"})


@node("submit", retries=2)
async def submit(state: dict, deps: Deps) -> dict:
    pv = state["preview"]
    token = state["approvals"][-1].get("approval_token")
    r = await deps.call("submitter", "submit_proposal", {"proposal_id": pv["proposal_id"], "idempotency_key": pv["submit_key"],
                                                         "dry_run": False, "approval_token": token})
    res = SubmissionResult(proposal_id=r.get("proposal_id"), status=r.get("status", "submitted"), connects_spent=r.get("connects_spent") or 0,
                           idempotency_key=pv["submit_key"], replay=bool(r.get("replay")))
    return {"submission": res.model_dump(), "status": "submitted" if "confirm" not in res.status else "awaiting_confirmation_on_upwork",
            "status_reason": f"proposal {res.proposal_id} {res.status}"}


async def dead_letter(state: dict, config: RunnableConfig) -> dict:
    deps: Deps = config["configurable"]["deps"]
    deps.emit("dead_letter", "dead_letter", {"reason": state.get("status_reason")})
    return {"status": "dead_letter"}


async def needs_attention(state: dict, config: RunnableConfig) -> dict:
    deps: Deps = config["configurable"]["deps"]
    deps.emit("needs_attention", "needs_attention", {"reason": state.get("status_reason")})
    return {"status": "needs_attention"}
