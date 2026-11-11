"""Internal tokens.

* MCP bearer tokens: short-lived JWTs (sub=user_id, persona, marketplace credentials reference) signed with
  GIGBID_SECRET. The API mints one per graph run; MCP servers verify the signature (no DB round-trip).
* Approval tokens: HMAC over (user, action, payload hash). Minted ONLY by the API when a human approves in the UI;
  marketplace write tools refuse non-dry-run calls without a valid token (R4 enforced at the tool layer).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time

import jwt

ALG = "HS256"


def secret() -> str:
    s = os.environ.get("GIGBID_SECRET")
    if not s:
        s = "dev-only-secret-change-me-0123456789abcdef"
    return s


def mint_mcp_token(user_id: str, persona: str, gigsim_key: str | None, mode: str = "gigsim", ttl_s: int = 3600) -> str:
    return jwt.encode({"sub": user_id, "persona": persona, "gk": gigsim_key, "mode": mode, "exp": int(time.time()) + ttl_s,
                       "aud": "gigbid-mcp"}, secret(), algorithm=ALG)


def verify_mcp_token(token: str) -> dict:
    return jwt.decode(token, secret(), algorithms=[ALG], audience="gigbid-mcp")


def payload_hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def mint_approval(user_id: str, action: str, payload: dict) -> str:
    msg = f"{user_id}|{action}|{payload_hash(payload)}".encode()
    return hmac.new(secret().encode(), msg, hashlib.sha256).hexdigest()


def verify_approval(token: str | None, user_id: str, action: str, payload: dict) -> bool:
    if not token:
        return False
    return hmac.compare_digest(token, mint_approval(user_id, action, payload))
