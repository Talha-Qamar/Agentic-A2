"""GigBid Workspace MCP server: a local mock calendar and email drafts (no Google account needed).

Tools: free_slots (read), create_interview_hold (write, idempotent, dry_run), create_email_draft (write, idempotent).
Slots respect the user's working hours and time zone (users.settings.working_hours / timezone).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from common import db
from common.audit import audit
from common.tokens import verify_mcp_token

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)


class Slot(BaseModel):
    start: str = Field(description="ISO 8601 with offset")
    end: str
    label: str = Field(description="human-readable, in the freelancer's time zone")


class Slots(BaseModel):
    timezone: str
    slots: list[Slot]


class HoldResult(BaseModel):
    dry_run: bool
    event_id: str | None = None
    start: str
    end: str
    title: str
    replay: bool = False


class DraftResult(BaseModel):
    dry_run: bool
    draft_id: str | None = None
    subject: str
    replay: bool = False


def _user(ctx: Context | None) -> tuple[str, str | None]:
    trace = None
    try:
        req = ctx.request_context.request
        trace = req.headers.get("x-trace-id")
        auth = req.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            return verify_mcp_token(auth[7:])["sub"], trace
    except Exception:  # noqa: BLE001
        pass
    if os.environ.get("WORKSPACE_ALLOW_ANON") == "1":
        return "local", trace
    raise ValueError("unauthorized: missing bearer token")


def _prefs(user_id: str) -> tuple[str, int, int]:
    r = db.one("SELECT settings FROM users WHERE user_id=%s", (user_id,))
    s = (r or {}).get("settings") or {}
    wh = s.get("working_hours", [10, 18])
    return s.get("timezone", "Asia/Karachi"), int(wh[0]), int(wh[1])


def _seed_busy(user_id: str, tz: ZoneInfo, start_day: date, days: int) -> None:
    """Deterministic mock calendar: a daily stand-up and a few random busy blocks per user."""
    for d in range(days):
        day = start_day + timedelta(days=d)
        rng = random.Random(f"{user_id}-{day.isoformat()}")
        blocks = [(11, 0, 30, "Team stand-up")]
        for _ in range(rng.randint(0, 2)):
            blocks.append((rng.choice([13, 14, 15, 16]), rng.choice([0, 30]), rng.choice([60, 90]), "Client work"))
        for h, m, dur, title in blocks:
            st = datetime(day.year, day.month, day.day, h, m, tzinfo=tz)
            key = hashlib.sha1(f"seed|{user_id}|{st.isoformat()}|{title}".encode()).hexdigest()[:24]
            db.x("INSERT INTO calendar_events(event_id,user_id,start_ts,end_ts,title,kind,idempotency_key) VALUES "
                 "(%s,%s,%s,%s,%s,'busy',%s) ON CONFLICT DO NOTHING", ("ev-" + key[:12], user_id, st, st + timedelta(minutes=dur), title, key))


def free_slots_for(user_id: str, days: int = 5, duration_min: int = 30, max_slots: int = 6, start: date | None = None) -> Slots:
    tzname, h0, h1 = _prefs(user_id)
    tz = ZoneInfo(tzname)
    first = start or (datetime.now(tz) + timedelta(days=1)).date()
    _seed_busy(user_id, tz, first, days + 3)
    busy = db.q("SELECT start_ts, end_ts FROM calendar_events WHERE user_id=%s AND end_ts > %s",
                (user_id, datetime(first.year, first.month, first.day, tzinfo=tz)))
    out, d = [], 0
    while len(out) < max_slots and d < days + 3:
        day = first + timedelta(days=d)
        d += 1
        if day.weekday() >= 5:
            continue
        t = datetime(day.year, day.month, day.day, h0, 0, tzinfo=tz)
        end_day = datetime(day.year, day.month, day.day, h1, 0, tzinfo=tz)
        per_day = 0
        while t + timedelta(minutes=duration_min) <= end_day and per_day < 2 and len(out) < max_slots:
            e = t + timedelta(minutes=duration_min)
            if not any(b["start_ts"] < e and b["end_ts"] > t for b in busy):
                out.append(Slot(start=t.isoformat(), end=e.isoformat(), label=t.strftime("%a %d %b, %H:%M") + f" ({tzname})"))
                per_day += 1
                t += timedelta(minutes=150)
            else:
                t += timedelta(minutes=30)
    return Slots(timezone=tzname, slots=out)


def build_server(**kw) -> FastMCP:
    mcp = FastMCP("gigbid-workspace", stateless_http=True, json_response=True,
                  instructions="The freelancer's calendar and email drafts. Propose only slots returned by free_slots.", **kw)

    @mcp.tool(annotations=READ, title="Find free interview slots")
    def free_slots(days: int = Field(5, ge=1, le=14), duration_min: int = Field(30, ge=15, le=120),
                   max_slots: int = Field(6, ge=1, le=12), ctx: Context = None) -> Slots:
        """Free slots in the freelancer's working hours and time zone over the next `days` days."""
        uid, trace = _user(ctx)
        out = free_slots_for(uid, days, duration_min, max_slots)
        audit("workspace", "free_slots", uid, {"days": days, "duration_min": duration_min}, {"n": len(out.slots)}, "ok", trace)
        return out

    @mcp.tool(annotations=WRITE, title="Create a tentative interview hold")
    def create_interview_hold(start: str = Field(description="ISO 8601 start from free_slots"), duration_min: int = Field(30, ge=15, le=120),
                              title: str = Field(max_length=120), idempotency_key: str = Field(min_length=16, max_length=128),
                              dry_run: bool = False, ctx: Context = None) -> HoldResult:
        """Block a tentative calendar hold for an interview. Idempotent by key."""
        uid, trace = _user(ctx)
        st = datetime.fromisoformat(start)
        en = st + timedelta(minutes=duration_min)
        if dry_run:
            return HoldResult(dry_run=True, start=st.isoformat(), end=en.isoformat(), title=title)
        ex = db.one("SELECT event_id FROM calendar_events WHERE user_id=%s AND idempotency_key=%s", (uid, idempotency_key))
        if ex:
            return HoldResult(dry_run=False, event_id=ex["event_id"], start=st.isoformat(), end=en.isoformat(), title=title, replay=True)
        eid = "ev-" + uuid.uuid4().hex[:12]
        db.x("INSERT INTO calendar_events(event_id,user_id,start_ts,end_ts,title,kind,idempotency_key) VALUES (%s,%s,%s,%s,%s,'tentative',%s)",
             (eid, uid, st, en, title, idempotency_key))
        audit("workspace", "create_interview_hold", uid, {"start": start, "title": title}, {"event_id": eid}, "ok", trace)
        return HoldResult(dry_run=False, event_id=eid, start=st.isoformat(), end=en.isoformat(), title=title)

    @mcp.tool(annotations=WRITE, title="Create an email draft")
    def create_email_draft(to_alias: str = Field(max_length=120, description="recipient name or alias, not an address"),
                           subject: str = Field(max_length=200), body: str = Field(max_length=5000),
                           idempotency_key: str = Field(min_length=16, max_length=128), dry_run: bool = False,
                           ctx: Context = None) -> DraftResult:
        """Save an email draft for the freelancer to review (never sent automatically)."""
        uid, trace = _user(ctx)
        if dry_run:
            return DraftResult(dry_run=True, subject=subject)
        ex = db.one("SELECT draft_id FROM email_drafts WHERE user_id=%s AND idempotency_key=%s", (uid, idempotency_key))
        if ex:
            return DraftResult(dry_run=False, draft_id=ex["draft_id"], subject=subject, replay=True)
        did = "ed-" + uuid.uuid4().hex[:12]
        db.x("INSERT INTO email_drafts(draft_id,user_id,to_alias,subject,body,idempotency_key) VALUES (%s,%s,%s,%s,%s,%s)",
             (did, uid, to_alias, subject, body, idempotency_key))
        audit("workspace", "create_email_draft", uid, {"to": to_alias, "subject": subject}, {"draft_id": did}, "ok", trace)
        return DraftResult(dry_run=False, draft_id=did, subject=subject)

    return mcp


def http_app(mcp=None):
    return (mcp or build_server()).streamable_http_app()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transport", choices=["stdio", "http"], default="http")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8203")))
    a = ap.parse_args()
    if a.transport == "stdio":
        os.environ.setdefault("WORKSPACE_ALLOW_ANON", "1")
        build_server().run("stdio")
    else:
        import uvicorn
        uvicorn.run(http_app(), host="0.0.0.0", port=a.port)


if __name__ == "__main__":
    json  # noqa: B018
    main()
