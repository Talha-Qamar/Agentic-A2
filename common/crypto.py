"""Encrypted OAuth token store (Fernet, key from GIGBID_TOKEN_KEY). Tokens are never logged."""
from __future__ import annotations

import base64
import hashlib
import json
import os

from cryptography.fernet import Fernet


def _fernet() -> Fernet:
    raw = os.environ.get("GIGBID_TOKEN_KEY") or os.environ.get("GIGBID_SECRET", "dev-only-secret-change-me")
    key = raw.encode() if len(raw) == 44 and raw.endswith("=") else base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(key)


def encrypt(obj: dict) -> bytes:
    return _fernet().encrypt(json.dumps(obj).encode())


def decrypt(blob: bytes) -> dict:
    return json.loads(_fernet().decrypt(bytes(blob)).decode())


def save_token(user_id: str, provider: str, token: dict) -> None:
    from common import db
    db.x("INSERT INTO oauth_tokens(user_id, provider, ciphertext) VALUES (%s,%s,%s) ON CONFLICT (user_id, provider) "
         "DO UPDATE SET ciphertext=EXCLUDED.ciphertext, updated_at=now()", (user_id, provider, encrypt(token)))


def load_token(user_id: str, provider: str) -> dict | None:
    from common import db
    r = db.one("SELECT ciphertext FROM oauth_tokens WHERE user_id=%s AND provider=%s", (user_id, provider))
    return decrypt(r["ciphertext"]) if r else None


def delete_token(user_id: str, provider: str) -> None:
    from common import db
    db.x("DELETE FROM oauth_tokens WHERE user_id=%s AND provider=%s", (user_id, provider))
