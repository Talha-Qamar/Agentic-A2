from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field

from apps.api.auth.session import COOKIE, UserDep, check_pw, create_user, make_session
from common import db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(min_length=1, max_length=200)


class RegisterIn(LoginIn):
    name: str = Field(min_length=1, max_length=100)


class Me(BaseModel):
    user_id: str
    email: str
    name: str | None
    persona: str
    marketplace_mode: str
    onboarded: bool
    settings: dict


def _set(resp: Response, uid: str) -> None:
    resp.set_cookie(COOKIE, make_session(uid), httponly=True, samesite="lax", max_age=7 * 86400, secure=False)


@router.post("/login", response_model=Me)
def login(body: LoginIn, response: Response):
    u = db.one("SELECT * FROM users WHERE email=%s", (body.email.lower(),))
    if not u or not check_pw(body.password, u["password_hash"]):
        raise HTTPException(401, "wrong email or password")
    _set(response, u["user_id"])
    return Me(**{k: u[k] for k in Me.model_fields})


@router.post("/register", response_model=Me)
def register(body: RegisterIn, response: Response):
    if db.one("SELECT 1 FROM users WHERE email=%s", (body.email.lower(),)):
        raise HTTPException(409, "email already registered")
    u = create_user(body.email, body.password, body.name)
    _set(response, u["user_id"])
    return Me(**{k: u[k] for k in Me.model_fields})


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE)
    return {"ok": True}


@router.get("/me", response_model=Me)
def me(user=UserDep):
    return Me(**{k: user[k] for k in Me.model_fields})


EmailStr  # noqa: B018
