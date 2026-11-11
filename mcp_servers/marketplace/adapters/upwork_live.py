"""Live Upwork adapter: the official Upwork MCP server (https://mcp.upwork.com/mcp) over Streamable HTTP with
OAuth 2.1, mapped onto the same marketplace port as GigSim so the graph cannot tell which one it uses.

Rules enforced here (A4, platform terms):
* read tools only on the conservative schedule set in config (marketplace.live_poll_minutes) - no scraping;
* proposals and messages are created ONLY as Upwork drafts after approval in GigBid; the user confirms them on
  Upwork. `submit_proposal` therefore never submits: it returns status "awaiting_confirmation_on_upwork";
* no browser automation, no cookies; tokens are stored encrypted per user (common/crypto.py) and never logged.

The OAuth flow uses the MCP Python SDK's OAuthClientProvider (discovery, dynamic client registration, PKCE).
Upwork's tool names are mapped in upwork_tool_map.yaml; unmapped tools are discovered by keyword at connect time.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import yaml

from agent.marketplace_port import MarketplaceError, MarketplaceUnavailable

UPWORK_MCP_URL = "https://mcp.upwork.com/mcp"
TOOL_MAP = yaml.safe_load((Path(__file__).parent / "upwork_tool_map.yaml").read_text())


class EncryptedTokenStorage:
    """mcp.client.auth.TokenStorage backed by the encrypted oauth_tokens table."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    async def get_tokens(self):
        from mcp.shared.auth import OAuthToken

        from common.crypto import load_token
        d = load_token(self.user_id, "upwork")
        return OAuthToken(**d["tokens"]) if d and d.get("tokens") else None

    async def set_tokens(self, tokens) -> None:
        from common.crypto import load_token, save_token
        d = load_token(self.user_id, "upwork") or {}
        d["tokens"] = tokens.model_dump(mode="json")
        save_token(self.user_id, "upwork", d)

    async def get_client_info(self):
        from mcp.shared.auth import OAuthClientInformationFull

        from common.crypto import load_token
        d = load_token(self.user_id, "upwork")
        return OAuthClientInformationFull(**d["client"]) if d and d.get("client") else None

    async def set_client_info(self, info) -> None:
        from common.crypto import load_token, save_token
        d = load_token(self.user_id, "upwork") or {}
        d["client"] = info.model_dump(mode="json")
        save_token(self.user_id, "upwork", d)


class PendingAuth:
    """Bridges the SDK's redirect/callback handlers to two HTTP endpoints of the GigBid API."""
    pending: dict[str, "PendingAuth"] = {}

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.auth_url: asyncio.Future = asyncio.get_event_loop().create_future()
        self.code: asyncio.Future = asyncio.get_event_loop().create_future()
        PendingAuth.pending[user_id] = self

    async def redirect_handler(self, url: str) -> None:
        if not self.auth_url.done():
            self.auth_url.set_result(url)

    async def callback_handler(self) -> tuple[str, str | None]:
        return await asyncio.wait_for(self.code, timeout=600)


def oauth_provider(user_id: str, redirect_uri: str, pending: PendingAuth | None = None):
    from mcp.client.auth import OAuthClientProvider
    from mcp.shared.auth import OAuthClientMetadata
    meta = OAuthClientMetadata(client_name="GigBid", redirect_uris=[redirect_uri], grant_types=["authorization_code", "refresh_token"],
                               response_types=["code"], token_endpoint_auth_method="none")
    pending = pending or PendingAuth(user_id)

    async def no_interactive() -> tuple[str, str | None]:
        raise MarketplaceError("upwork_not_connected", "connect Upwork in Settings first")
    return OAuthClientProvider(server_url=UPWORK_MCP_URL, client_metadata=meta, storage=EncryptedTokenStorage(user_id),
                               redirect_handler=pending.redirect_handler, callback_handler=pending.callback_handler)


async def start_oauth(user_id: str, redirect_uri: str) -> str:
    """Kick off the OAuth flow; returns the Upwork authorization URL the UI should open."""
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    pending = PendingAuth(user_id)
    auth = oauth_provider(user_id, redirect_uri, pending)

    async def connect():
        async with streamablehttp_client(UPWORK_MCP_URL, auth=auth) as (r, w, _):
            async with ClientSession(r, w) as s:
                await s.initialize()
                await s.list_tools()
    pending.task = asyncio.create_task(connect())
    return await asyncio.wait_for(pending.auth_url, timeout=30)


def finish_oauth(user_id: str, code: str, state: str | None) -> bool:
    p = PendingAuth.pending.get(user_id)
    if not p or p.code.done():
        return False
    p.code.set_result((code, state))
    return True


class UpworkLiveAdapter:
    name = "upwork_live"

    def __init__(self, user_id: str, redirect_uri: str = "http://localhost:8000/api/auth/upwork/callback"):
        self.user_id = user_id
        self.redirect_uri = redirect_uri
        self._tools: dict | None = None

    async def _session_call(self, logical: str, args: dict) -> dict:
        from langchain_mcp_adapters.client import MultiServerMCPClient
        try:
            if self._tools is None:
                client = MultiServerMCPClient({"upwork": {"transport": "streamable_http", "url": UPWORK_MCP_URL,
                                                          "auth": oauth_provider(self.user_id, self.redirect_uri)}})
                self._tools = {t.name: t for t in await client.get_tools()}
            name = resolve_tool(logical, list(self._tools))
            if not name:
                raise MarketplaceError("unsupported_in_live_mode", logical)
            out = await self._tools[name].ainvoke(map_args(logical, args))
        except MarketplaceError:
            raise
        except Exception as e:  # noqa: BLE001
            raise MarketplaceUnavailable(f"upwork: {type(e).__name__}: {e}") from e
        if isinstance(out, str):
            try:
                return json.loads(out)
            except json.JSONDecodeError:
                return {"text": out}
        return out if isinstance(out, dict) else {"result": out}

    async def search_jobs(self, query="", category=None, limit=20, since_minute=None, pool="stream", persona=None):
        res = await self._session_call("search_jobs", {"query": query, "limit": limit, "category": category})
        jobs = res.get("jobs") or res.get("results") or res.get("data") or []
        return {"total": len(jobs), "jobs": [normalise_job(j) for j in jobs]}

    async def get_job(self, job_id):
        return normalise_job(await self._session_call("get_job", {"job_id": job_id}))

    async def get_client_history(self, client_id):
        return await self._session_call("get_client", {"client_id": client_id})

    async def get_connects_balance(self):
        return await self._session_call("get_connects", {})

    async def get_market_stats(self, category=None):
        # Upwork exposes no market statistics; GigBid uses the bundled Kaggle-derived stats for pricing.
        from pathlib import Path as _P
        s = json.loads((_P(__file__).resolve().parents[3] / "gigsim" / "seed_data" / "market_stats.json").read_text())
        return {"category": category, "hourly": s["hourly"].get(category, s["hourly_all"]), "fixed": s["fixed"].get(category, s["fixed_all"]),
                "source": s["source"] + " (offline stats; Upwork MCP has no market-stats tool)"}

    async def get_policy(self):
        return {"version": "upwork-live", "rules": [], "requirements": {"ai_disclosure": False}, "limits": {"daily_proposal_cap": None}}

    async def list_threads(self):
        return await self._session_call("list_rooms", {})

    async def list_messages(self, thread_id):
        return await self._session_call("list_messages", {"room_id": thread_id})

    async def list_proposals(self, status=None):
        return await self._session_call("list_proposals", {"status": status})

    async def get_events(self, since_id=0):
        return {"events": []}

    async def create_proposal_draft(self, job_id, cover_letter, bid_amount, bid_type, screening_answers, idempotency_key):
        res = await self._session_call("create_proposal_draft", {"job_id": job_id, "cover_letter": cover_letter, "amount": bid_amount,
                                                                  "answers": screening_answers})
        return {"proposal_id": res.get("id") or res.get("proposal_id") or idempotency_key, "status": "draft_on_upwork", "raw": res}

    async def submit_proposal(self, proposal_id, idempotency_key, dry_run):
        # Upwork requires the freelancer to confirm drafts on Upwork itself. GigBid never submits in live mode.
        return {"proposal_id": proposal_id, "status": "awaiting_confirmation_on_upwork", "dry_run": dry_run,
                "connects_cost": None, "note": "Open Upwork to review and confirm this draft."}

    async def send_message(self, thread_id, text, idempotency_key, dry_run):
        if dry_run:
            return {"dry_run": True, "would_send": {"thread_id": thread_id, "text": text}}
        res = await self._session_call("draft_message", {"room_id": thread_id, "message": text})
        return {"status": "draft_on_upwork", "raw": res}


def resolve_tool(logical: str, available: list[str]) -> str | None:
    for cand in TOOL_MAP["tools"].get(logical, {}).get("names", []):
        if cand in available:
            return cand
    kws = TOOL_MAP["tools"].get(logical, {}).get("keywords", [])
    for name in available:
        if kws and all(k in name.lower() for k in kws):
            return name
    return None


def map_args(logical: str, args: dict) -> dict:
    ren = TOOL_MAP["tools"].get(logical, {}).get("args", {})
    return {ren.get(k, k): v for k, v in args.items() if v is not None}


def normalise_job(j: dict) -> dict:
    budget = j.get("budget") or {}
    return {"job_id": str(j.get("id") or j.get("job_id") or j.get("ciphertext")), "title": j.get("title", ""),
            "description": j.get("description") or j.get("snippet") or "", "category": j.get("category") or j.get("occupation"),
            "skills": [s if isinstance(s, str) else s.get("name", "") for s in (j.get("skills") or [])],
            "budget_type": "hourly" if (j.get("type") or j.get("job_type") or "").lower().startswith("hour") else "fixed",
            "budget_max": budget.get("amount") if isinstance(budget, dict) else budget, "screening_questions": j.get("questions") or [],
            "client": j.get("client") or {}, "source": "upwork"}
