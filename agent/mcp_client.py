"""MCP client for the graph (langchain-mcp-adapters).

One MultiServerMCPClient per run carries that run's bearer token, user and trace id as headers, so the
MCP servers' audit logs share the trace id of the UI request.  Each agent only receives the tools on its
allowlist (agent/config.yaml mcp.allowlists).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from agent import settings
from agent.tracing import current_trace_id, span


class ToolCallError(RuntimeError):
    pass


SERVERS = {"portfolio": "mcp.portfolio_url", "marketplace": "mcp.marketplace_url", "workspace": "mcp.workspace_url"}


async def load_tools(user_id: str, token: str, servers: tuple[str, ...] = ("portfolio", "marketplace", "workspace"),
                     trace_id: str | None = None) -> dict[str, Any]:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    headers = {"Authorization": f"Bearer {token}", "X-Trace-Id": trace_id or current_trace_id(), "X-GigBid-User": user_id}
    conns = {s: {"transport": "streamable_http", "url": settings.get(SERVERS[s]), "headers": dict(headers),
                 "timeout": settings.get("mcp.call_timeout_s", 30)} for s in servers}
    client = MultiServerMCPClient(conns)
    tools = await client.get_tools()
    return {t.name: t for t in tools}


def allowlisted(tools: dict[str, Any], agent: str) -> dict[str, Any]:
    allow = set(settings.get(f"mcp.allowlists.{agent}", []))
    return {n: t for n, t in tools.items() if n in allow}


def parse_result(out: Any) -> Any:
    if isinstance(out, tuple):
        out = out[0]
    if isinstance(out, list):
        texts = [b.get("text", "") if isinstance(b, dict) else getattr(b, "text", str(b)) for b in out]
        out = "".join(texts)
    if isinstance(out, str):
        s = out.strip()
        if s.startswith(("{", "[")):
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                return {"text": s}
        if s.lower().startswith("error"):
            raise ToolCallError(s)
        return {"text": s}
    return out


async def call_tool(tools: dict[str, Any], name: str, args: dict) -> Any:
    if name not in tools:
        raise ToolCallError(f"tool {name} not available to this agent")
    retries = settings.get("mcp.retries", 2)
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with span(f"mcp.{name}", {"mcp.tool": name}):
                out = await asyncio.wait_for(tools[name].ainvoke(args), timeout=settings.get("mcp.call_timeout_s", 30) + 5)
            res = parse_result(out)
            if isinstance(res, dict) and res.get("text", "").startswith("Error"):
                raise ToolCallError(res["text"])
            return res
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            last = e
            if any(k in msg for k in ("approval_required", "policy_violation", "not_found", "unauthorized", "validation",
                                      "insufficient_connects", "daily_proposal_cap", "conflict")):
                raise ToolCallError(msg) from e
            await asyncio.sleep(0.5 * 2 ** attempt)
    raise ToolCallError(f"{name} failed after retries: {last}")
