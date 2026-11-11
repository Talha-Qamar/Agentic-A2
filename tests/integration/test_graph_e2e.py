"""Integration: bid graph + conversation graph against real GigSim and MCP servers (stub model, no network)."""
import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


@pytest.fixture(scope="module")
def stack():
    import run_stack
    os.environ["GIGSIM_DB"] = str(ROOT / "var" / "it_gigsim.db")
    for p in (ROOT / "var").glob("it_gigsim.db*"):
        p.unlink()
    os.environ["GIGBID_CHECKPOINTER"] = "memory"
    ps = run_stack.start({"GIGSIM_DB": os.environ["GIGSIM_DB"], "GIGSIM_ERROR_RATE": "0"})
    yield
    run_stack.stop(ps)


@pytest.mark.integration
def test_bid_to_submit_exactly_once_then_reply(stack):
    from agent import settings
    saved = dict(settings.cfg()["thresholds"])
    settings.cfg()["thresholds"]["fit_bid"] = 0.0
    settings.cfg()["thresholds"]["fit_watch"] = 0.0
    try:
        _flow(settings, ROOT)
    finally:
        settings.cfg()["thresholds"].update(saved)


def _flow(settings, ROOT):
    from agent.runner import approval_token_for, message_token_for, resume_bid, resume_conversation, run_bid, run_conversation
    jobs = [json.loads(line) for line in open(ROOT / "evals" / "datasets" / "dev_set.jsonl")]
    job = next(j for j in jobs if j["persona"] == "ai_ml_engineer" and j["labels"]["gold_decision"] == "bid" and j["budget_type"] == "fixed")
    user = {"user_id": "u-it", "persona": "ai_ml_engineer", "gigsim_key": "gs-key-ai_ml_engineer"}
    out = asyncio.run(run_bid(user, {"job_id": job["job_id"]}))
    assert out["status"] == "awaiting_approval" and out["pending_approval"]["connects_cost"] > 0
    p = out["pending_approval"]
    # submitting without the human approval token is refused by the marketplace server
    from agent.mcp_client import ToolCallError  # noqa: F401
    done = asyncio.run(resume_bid(user, out["thread_id"], {"action": "approve", "approval_token": approval_token_for("u-it", p)}))
    assert done["status"] == "submitted" and done["submission"]["connects_spent"] > 0
    H = {"X-GigSim-Key": "gs-key-ai_ml_engineer"}
    httpx.post("http://localhost:8100/v1/admin/flush", headers={"X-Admin-Key": "gigsim-admin"})
    th = httpx.get("http://localhost:8100/v1/threads", headers=H).json()["threads"]
    if th:
        c = asyncio.run(run_conversation(user, th[0]["thread_id"]))
        assert c["status"] in ("awaiting_approval", "blocked"), (c["status"], c.get("errors"))
        if c["pending_approval"]:
            sent = asyncio.run(resume_conversation(user, c["thread_id"], {"action": "approve", "approval_token": message_token_for("u-it", c["pending_approval"])}))
            assert sent["status"] == "sent"


@pytest.mark.integration
def test_submit_without_approval_token_is_refused(stack):
    from agent.mcp_client import call_tool, load_tools
    from common.tokens import mint_mcp_token
    tools = asyncio.run(load_tools("u-it2", mint_mcp_token("u-it2", "ai_ml_engineer", "gs-key-ai_ml_engineer"), servers=("marketplace",)))
    with pytest.raises(Exception) as e:
        asyncio.run(call_tool(tools, "submit_proposal", {"proposal_id": "pr-anything", "idempotency_key": "x" * 20, "dry_run": False}))
    assert "approval_required" in str(e.value)
