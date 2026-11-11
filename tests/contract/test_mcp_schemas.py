"""Contract tests: the MCP tool surface (names, input/output schemas, annotations) matches the committed snapshot.
Regenerate intentionally with: UPDATE_SNAPSHOTS=1 pytest tests/contract"""
import asyncio
import json
import os
from pathlib import Path

import pytest

SNAP = Path(__file__).parent / "mcp_schema_snapshot.json"


def surface():
    from mcp_servers.marketplace.server import build_server as mk
    from mcp_servers.portfolio.server import build_server as pf
    from mcp_servers.workspace.server import build_server as ws
    out = {}
    for name, b in (("portfolio", pf), ("marketplace", mk), ("workspace", ws)):
        tools = asyncio.run(b().list_tools())
        out[name] = {t.name: {"input": t.inputSchema, "output": t.outputSchema,
                              "annotations": t.annotations.model_dump(exclude_none=True) if t.annotations else None} for t in tools}
    return out


@pytest.mark.contract
def test_schema_snapshot():
    cur = surface()
    if os.environ.get("UPDATE_SNAPSHOTS") or not SNAP.exists():
        SNAP.write_text(json.dumps(cur, indent=1, sort_keys=True))
    assert cur == json.loads(SNAP.read_text())


@pytest.mark.contract
def test_write_tools_have_idempotency_dry_run_and_annotations():
    cur = surface()
    for server, tool in (("marketplace", "submit_proposal"), ("marketplace", "send_message"), ("marketplace", "create_proposal_draft"),
                         ("workspace", "create_interview_hold")):
        t = cur[server][tool]
        props = t["input"]["properties"]
        assert "idempotency_key" in props and "dry_run" in props
        assert t["annotations"]["readOnlyHint"] is False and t["annotations"]["idempotentHint"] is True
    assert cur["marketplace"]["submit_proposal"]["annotations"]["destructiveHint"] is True
    for name, t in cur["portfolio"].items():
        assert t["annotations"]["readOnlyHint"] is True and t["output"] is not None
