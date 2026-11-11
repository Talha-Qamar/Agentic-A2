"""The single marketplace interface (R1).

Agents and graph nodes talk only to ``MarketplacePort``.  The port calls the GigBid Marketplace MCP server,
which delegates to one of two adapters chosen by config (``marketplace.mode``):

    mcp_servers/marketplace/adapters/gigsim.py       GigSim REST simulator
    mcp_servers/marketplace/adapters/upwork_live.py  official Upwork MCP server (OAuth 2.1, Streamable HTTP)

Nothing in agent/ knows which marketplace is behind the port.  Errors are normalised into
``MarketplaceUnavailable`` (degraded mode: UI banner + work queued) and ``MarketplaceError``.
"""
from __future__ import annotations

from typing import Any, Protocol


class MarketplaceError(RuntimeError):
    def __init__(self, code: str, detail: Any = None):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class MarketplaceUnavailable(MarketplaceError):
    def __init__(self, detail: Any = None):
        super().__init__("marketplace_unavailable", detail)


class MarketplacePort(Protocol):
    # read
    async def search_jobs(self, query: str = "", category: str | None = None, limit: int = 20,
                          since_minute: float | None = None, pool: str = "stream") -> dict: ...
    async def get_job(self, job_id: str) -> dict: ...
    async def get_client_history(self, client_id: str) -> dict: ...
    async def get_connects_balance(self) -> dict: ...
    async def get_market_stats(self, category: str | None) -> dict: ...
    async def get_policy(self) -> dict: ...
    async def list_threads(self) -> dict: ...
    async def list_messages(self, thread_id: str) -> dict: ...
    async def list_proposals(self, status: str | None = None) -> dict: ...
    async def get_events(self, since_id: int = 0) -> dict: ...
    # write (drafts first; submits/sends require an approval token from the human approval step)
    async def create_proposal_draft(self, job_id: str, cover_letter: str, bid_amount: float, bid_type: str,
                                    screening_answers: list[str], idempotency_key: str, dry_run: bool = False) -> dict: ...
    async def submit_proposal(self, proposal_id: str, idempotency_key: str, dry_run: bool = True,
                              approval_token: str | None = None) -> dict: ...
    async def send_message(self, thread_id: str, text: str, idempotency_key: str, dry_run: bool = True,
                           approval_token: str | None = None) -> dict: ...


class McpMarketplace:
    """MarketplacePort implementation over the Marketplace MCP server (the only implementation agents use)."""

    def __init__(self, tools: dict[str, Any]):
        self.tools = tools  # name -> LangChain tool from langchain-mcp-adapters (already allowlisted)

    async def _call(self, name: str, **args) -> dict:
        from agent.mcp_client import call_tool
        return await call_tool(self.tools, name, {k: v for k, v in args.items() if v is not None})

    async def search_jobs(self, query="", category=None, limit=20, since_minute=None, pool="stream"):
        return await self._call("search_jobs", query=query, category=category, limit=limit, since_minute=since_minute, pool=pool)

    async def get_job(self, job_id):
        return await self._call("get_job", job_id=job_id)

    async def get_client_history(self, client_id):
        return await self._call("get_client_history", client_id=client_id)

    async def get_connects_balance(self):
        return await self._call("get_connects_balance")

    async def get_market_stats(self, category):
        return await self._call("get_market_stats", category=category)

    async def get_policy(self):
        return await self._call("get_policy")

    async def list_threads(self):
        return await self._call("list_threads")

    async def list_messages(self, thread_id):
        return await self._call("list_messages", thread_id=thread_id)

    async def list_proposals(self, status=None):
        return await self._call("list_proposals", status=status)

    async def get_events(self, since_id=0):
        return await self._call("get_events", since_id=since_id)

    async def create_proposal_draft(self, job_id, cover_letter, bid_amount, bid_type, screening_answers, idempotency_key, dry_run=False):
        return await self._call("create_proposal_draft", job_id=job_id, cover_letter=cover_letter, bid_amount=bid_amount,
                                bid_type=bid_type, screening_answers=screening_answers, idempotency_key=idempotency_key,
                                dry_run=dry_run)

    async def submit_proposal(self, proposal_id, idempotency_key, dry_run=True, approval_token=None):
        return await self._call("submit_proposal", proposal_id=proposal_id, idempotency_key=idempotency_key, dry_run=dry_run,
                                approval_token=approval_token)

    async def send_message(self, thread_id, text, idempotency_key, dry_run=True, approval_token=None):
        return await self._call("send_message", thread_id=thread_id, text=text, idempotency_key=idempotency_key,
                                dry_run=dry_run, approval_token=approval_token)
