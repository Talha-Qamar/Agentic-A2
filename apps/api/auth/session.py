"""Cookie-session auth (httpOnly JWT). Every router depends on `current_user`; every query is scoped by user_id."""
from __future__ import annotations

import os
import time
import uuid

import bcrypt
import jwt
from fastapi import Cookie, Depends, HTTPException, Request

from common import db
from common.tokens import secret

COOKIE = "gb_session"


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt(rounds=10)).decode()


def check_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), h.encode())
    except ValueError:
        return False


def make_session(user_id: str) -> str:
    return jwt.encode({"sub": user_id, "exp": int(time.time()) + 7 * 86400, "aud": "gigbid-web"}, secret(), algorithm="HS256")


def current_user(request: Request, gb_session: str | None = Cookie(None)) -> dict:
    tok = gb_session or (request.headers.get("authorization", "")[7:] if request.headers.get("authorization", "").startswith("Bearer ") else None)
    if not tok:
        raise HTTPException(401, "not signed in")
    try:
        uid = jwt.decode(tok, secret(), algorithms=["HS256"], audience="gigbid-web")["sub"]
    except jwt.PyJWTError:
        raise HTTPException(401, "session expired") from None
    u = db.one("SELECT user_id, email, name, persona, marketplace_mode, gigsim_key, settings, onboarded FROM users WHERE user_id=%s", (uid,))
    if not u:
        raise HTTPException(401, "unknown user")
    return u


def create_user(email: str, password: str, name: str, persona: str = "ai_ml_engineer", onboarded: bool = False) -> dict:
    uid = "u-" + uuid.uuid4().hex[:10]
    key = provision_gigsim_account(persona)
    db.x("INSERT INTO users(user_id, email, name, password_hash, persona, gigsim_key, onboarded, settings) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
         (uid, email.lower(), name, hash_pw(password), persona, key, onboarded, '{"autonomy": "suggest"}'))
    seed_searches(uid, persona)
    return db.one("SELECT * FROM users WHERE user_id=%s", (uid,))


def provision_gigsim_account(persona: str) -> str:
    """Each GigBid user gets their own GigSim account (own Connects, proposals, threads)."""
    import httpx

    from agent import settings
    try:
        r = httpx.post(settings.get("marketplace.gigsim_url").rstrip("/") + "/v1/admin/accounts", json={"persona": persona},
                       headers={"X-Admin-Key": os.environ.get("GIGSIM_ADMIN_KEY", "gigsim-admin")}, timeout=10)
        r.raise_for_status()
        return r.json()["api_key"]
    except Exception:  # noqa: BLE001 - GigSim down: fall back to the seeded persona account
        return f"gs-key-{persona}"


DEFAULT_SEARCHES = {
    "ai_ml_engineer": ["RAG LLM chatbot agent", "machine learning model", "computer vision detection", "forecasting NLP"],
    "fullstack_web_dev": ["React Next.js web app", "Node API backend", "Stripe payments dashboard", "mobile app"],
    "data_analyst": ["dashboard Power BI Tableau", "SQL dbt analytics", "forecast financial model", "survey analysis"],
}


def seed_searches(user_id: str, persona: str) -> None:
    db.x("DELETE FROM saved_searches WHERE user_id=%s", (user_id,))
    for q in DEFAULT_SEARCHES.get(persona, []):
        db.x("INSERT INTO saved_searches(search_id, user_id, query, interval_minutes) VALUES (%s,%s,%s,%s)",
             ("ss-" + uuid.uuid4().hex[:8], user_id, q, 30))


UserDep = Depends(current_user)
