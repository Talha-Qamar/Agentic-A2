"""GigSim adapter: REST calls with timeouts, bounded retries with backoff, Retry-After on 429."""
from __future__ import annotations

import asyncio
import os
import random

import httpx

from agent.marketplace_port import MarketplaceError, MarketplaceUnavailable


class GigSimAdapter:
    name = "gigsim"

    def __init__(self, api_key: str, base_url: str | None = None, timeout: float = 15.0, retries: int = 3):
        self.base = (base_url or os.environ.get("GIGSIM_URL", "http://localhost:8100")).rstrip("/")
        self.key = api_key
        self.timeout = timeout
        self.retries = retries

    async def _req(self, method: str, path: str, **kw) -> dict:
        last = None
        for attempt in range(self.retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as c:
                    r = await c.request(method, self.base + path, headers={"X-GigSim-Key": self.key}, **kw)
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout, httpx.RemoteProtocolError) as e:
                last = MarketplaceUnavailable(f"{type(e).__name__}: {e}")
                await asyncio.sleep(min(8, 0.5 * 2 ** attempt + random.random() * 0.3))
                continue
            if r.status_code == 429:
                body = _json(r)
                if isinstance(body.get("detail"), dict) and body["detail"].get("error") == "daily_proposal_cap":
                    raise MarketplaceError("daily_proposal_cap", body["detail"])
                wait = float(r.headers.get("Retry-After", "2"))
                last = MarketplaceError("rate_limited", body)
                await asyncio.sleep(min(wait, 20))
                continue
            if r.status_code >= 500:
                last = MarketplaceUnavailable(_json(r)) if r.status_code == 503 and "down" in r.text else MarketplaceError("upstream_5xx", _json(r))
                await asyncio.sleep(min(8, 0.5 * 2 ** attempt + random.random() * 0.3))
                continue
            if r.status_code >= 400:
                raise MarketplaceError({400: "bad_request", 401: "unauthorized", 402: "insufficient_connects", 404: "not_found",
                                        409: "conflict", 422: "policy_violation"}.get(r.status_code, f"http_{r.status_code}"),
                                       _json(r).get("detail", _json(r)))
            return _json(r)
        if isinstance(last, MarketplaceError) and last.code in ("upstream_5xx",):
            raise MarketplaceUnavailable(last.detail)
        raise last or MarketplaceUnavailable("unknown")

    # read
    async def search_jobs(self, query="", category=None, limit=20, since_minute=None, pool="stream", persona=None):
        params = {"q": query, "limit": limit, "pool": pool}
        if category:
            params["category"] = category
        if since_minute is not None:
            params["since_minute"] = since_minute
        if persona:
            params["persona"] = persona
        return await self._req("GET", "/v1/jobs", params=params)

    async def get_job(self, job_id):
        return await self._req("GET", f"/v1/jobs/{job_id}")

    async def get_client_history(self, client_id):
        return await self._req("GET", f"/v1/clients/{client_id}")

    async def get_connects_balance(self):
        return await self._req("GET", "/v1/account")

    async def get_market_stats(self, category=None):
        return await self._req("GET", "/v1/market/stats", params={"category": category} if category else {})

    async def get_policy(self):
        return await self._req("GET", "/v1/policy")

    async def list_threads(self):
        return await self._req("GET", "/v1/threads")

    async def list_messages(self, thread_id):
        return await self._req("GET", f"/v1/threads/{thread_id}/messages")

    async def list_proposals(self, status=None):
        return await self._req("GET", "/v1/proposals", params={"status": status} if status else {})

    async def get_events(self, since_id=0):
        return await self._req("GET", "/v1/events", params={"since_id": since_id})

    # write
    async def create_proposal_draft(self, job_id, cover_letter, bid_amount, bid_type, screening_answers, idempotency_key):
        return await self._req("POST", "/v1/proposals/drafts", json={
            "job_id": job_id, "cover_letter": cover_letter, "bid_amount": bid_amount, "bid_type": bid_type,
            "screening_answers": screening_answers, "idempotency_key": idempotency_key})

    async def submit_proposal(self, proposal_id, idempotency_key, dry_run):
        return await self._req("POST", f"/v1/proposals/{proposal_id}/submit", json={"idempotency_key": idempotency_key, "dry_run": dry_run})

    async def send_message(self, thread_id, text, idempotency_key, dry_run):
        return await self._req("POST", f"/v1/threads/{thread_id}/messages", json={"text": text, "idempotency_key": idempotency_key,
                                                                                    "dry_run": dry_run})


def _json(r: httpx.Response) -> dict:
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return {"text": r.text[:300]}
