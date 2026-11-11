"""Job inbox, job detail, manual analysis and scouting."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.api.auth.session import UserDep
from common import db
from worker.tasks import enqueue

router = APIRouter(prefix="/api", tags=["jobs"])


class JobRow(BaseModel):
    job_id: str
    title: str | None
    status: str
    action: str | None = None
    fit_score: float | None = None
    risk_score: float | None = None
    price: float | None = None
    connects_cost: int | None = None
    duplicate_of: str | None = None
    thread_id: str | None = None
    reason: str | None = None
    budget_type: str | None = None
    budget_max: float | None = None
    category: str | None = None
    updated_at: str | None = None


@router.get("/jobs", response_model=list[JobRow])
def inbox(user=UserDep, status: str | None = None, limit: int = 100):
    rows = db.q("SELECT * FROM jobs WHERE user_id=%s ORDER BY updated_at DESC LIMIT %s", (user["user_id"], min(limit, 300)))
    out = []
    for r in rows:
        s, d = r.get("summary") or {}, r.get("data") or {}
        if status and r["status"] != status:
            continue
        out.append(JobRow(job_id=r["job_id"], title=r["title"], status=r["status"], action=r["action"], fit_score=r["fit_score"],
                          risk_score=r["risk_score"], price=r["price"], connects_cost=((s.get("preview") or {}).get("connects_cost")),
                          duplicate_of=r["duplicate_of"], thread_id=r["thread_id"], reason=s.get("status_reason"),
                          budget_type=d.get("budget_type"), budget_max=d.get("budget_max"), category=d.get("category"),
                          updated_at=r["updated_at"].isoformat() if r.get("updated_at") else None))
    return out


@router.get("/jobs/{job_id}")
def job_detail(job_id: str, user=UserDep):
    r = db.one("SELECT * FROM jobs WHERE user_id=%s AND job_id=%s", (user["user_id"], job_id))
    if not r:
        raise HTTPException(404, "job not found")
    return {"job_id": job_id, "title": r["title"], "status": r["status"], "thread_id": r["thread_id"], "data": r["data"],
            "summary": r.get("summary") or {}, "duplicate_of": r["duplicate_of"]}


class AnalyseIn(BaseModel):
    force: bool = False


@router.post("/jobs/{job_id}/analyse")
async def analyse(job_id: str, body: AnalyseIn | None = None, user=UserDep):
    jid = await enqueue("analyse_job", user["user_id"], job_id, bool(body and body.force))
    db.x("UPDATE jobs SET status='queued', updated_at=now() WHERE user_id=%s AND job_id=%s", (user["user_id"], job_id))
    return {"queued": jid}


class ManualJobIn(BaseModel):
    job_id: str


@router.post("/jobs")
async def add_job(body: ManualJobIn, user=UserDep):
    db.x("INSERT INTO jobs(user_id, job_id, title, data, status) VALUES (%s,%s,%s,'{}','queued') ON CONFLICT DO NOTHING",
         (user["user_id"], body.job_id, body.job_id))
    return {"queued": await enqueue("analyse_job", user["user_id"], body.job_id)}


@router.post("/scout/run")
async def scout_now(user=UserDep):
    return {"queued": await enqueue("scout", user["user_id"])}


@router.get("/searches")
def searches(user=UserDep):
    return db.q("SELECT search_id, query, category, interval_minutes, enabled, last_run_at FROM saved_searches WHERE user_id=%s", (user["user_id"],))


class SearchIn(BaseModel):
    query: str
    category: str | None = None
    interval_minutes: int = 30


@router.post("/searches")
def add_search(body: SearchIn, user=UserDep):
    import uuid
    sid = "ss-" + uuid.uuid4().hex[:8]
    db.x("INSERT INTO saved_searches(search_id, user_id, query, category, interval_minutes) VALUES (%s,%s,%s,%s,%s)",
         (sid, user["user_id"], body.query[:200], body.category, max(10, body.interval_minutes)))
    return {"search_id": sid}


@router.delete("/searches/{search_id}")
def del_search(search_id: str, user=UserDep):
    db.x("DELETE FROM saved_searches WHERE user_id=%s AND search_id=%s", (user["user_id"], search_id))
    return {"ok": True}
