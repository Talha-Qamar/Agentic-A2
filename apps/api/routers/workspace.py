"""Pipeline board, messages, analytics, settings, memory, portfolio and Upwork connection."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from agent import settings
from apps.api.auth.session import UserDep, seed_searches
from common import db
from worker.tasks import enqueue

router = APIRouter(prefix="/api", tags=["workspace"])
STAGES = ["submitted", "viewed", "replied", "interview", "hired", "lost"]


@router.get("/pipeline")
def pipeline(user=UserDep):
    rows = db.q("SELECT * FROM pipeline WHERE user_id=%s ORDER BY updated_at DESC", (user["user_id"],))
    cols = {s: [] for s in STAGES}
    for r in rows:
        cols.setdefault(r["stage"], []).append({k: r[k] for k in ("proposal_id", "job_id", "title", "stage", "connects_spent", "bid_amount",
                                                                  "marketplace_thread_id", "thread_id")} | {"updated_at": r["updated_at"].isoformat()})
    return {"stages": STAGES, "columns": cols}


@router.post("/pipeline/sync")
async def sync(user=UserDep):
    return {"queued": await enqueue("sync_pipeline", user["user_id"])}


@router.get("/messages")
def messages(user=UserDep):
    convs = db.q("SELECT c.*, p.title FROM conversations c LEFT JOIN pipeline p ON p.user_id=c.user_id AND p.proposal_id=c.proposal_id "
                 "WHERE c.user_id=%s ORDER BY c.updated_at DESC", (user["user_id"],))
    pend = {a["thread_id"]: a for a in db.q("SELECT * FROM approvals WHERE user_id=%s AND status='pending' AND kind='message_approval'",
                                           (user["user_id"],))}
    return [dict(c) | {"pending_approval": pend.get(c.get("graph_thread_id"))} for c in convs]


@router.post("/messages/{marketplace_thread_id}/draft")
async def draft_reply(marketplace_thread_id: str, user=UserDep):
    return {"queued": await enqueue("converse", user["user_id"], marketplace_thread_id)}


@router.get("/analytics")
def analytics(user=UserDep):
    uid = user["user_id"]
    pipe = db.q("SELECT stage, count(*) n, sum(connects_spent) c FROM pipeline WHERE user_id=%s GROUP BY stage", (uid,))
    runs = db.q("SELECT kind, status, count(*) n, avg(cost_usd) cost, avg(latency_s) lat, sum(tokens) tok, "
                "percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_s) p95 FROM runs WHERE user_id=%s GROUP BY kind, status", (uid,))
    sent = sum(r["n"] for r in pipe)
    replied = sum(r["n"] for r in pipe if r["stage"] in ("replied", "interview", "hired"))
    hired = sum(r["n"] for r in pipe if r["stage"] == "hired")
    connects = sum(r["c"] or 0 for r in pipe)
    res_dir = settings.ROOT / "evals" / "results"
    evals = {}
    for name in ("rag_benchmark.json", "decision_eval.json", "multiagent_comparison.json", "tool_granularity.json", "injection_eval.json"):
        p = res_dir / name
        if p.exists():
            d = json.loads(p.read_text())
            evals[name] = d.get("summary") or d.get("headline")
    return {"proposals_sent": sent, "reply_rate": round(replied / sent, 3) if sent else None, "win_rate": round(hired / sent, 3) if sent else None,
            "connects_spent": connects, "connects_per_hire": round(connects / hired, 1) if hired else None,
            "by_stage": pipe, "runs": runs, "declared_budgets": settings.get("budgets.declared"), "evals": evals}


class SettingsIn(BaseModel):
    hourly_floor: float | None = Field(None, ge=1, le=1000)
    target_rate: float | None = Field(None, ge=1, le=2000)
    working_hours: list[int] | None = None
    timezone: str | None = None
    autonomy: str | None = Field(None, pattern="^(suggest|auto_skip)$")
    persona: str | None = Field(None, pattern="^(ai_ml_engineer|fullstack_web_dev|data_analyst)$")
    marketplace_mode: str | None = Field(None, pattern="^(gigsim|upwork_live)$")


@router.get("/settings")
def get_settings(user=UserDep):
    prof = json.loads((settings.ROOT / "data" / "personas" / user["persona"] / "profile.json").read_text())
    s = {"hourly_floor": prof["hourly_floor"], "target_rate": prof["target_rate"], "working_hours": [10, 18], "timezone": "Asia/Karachi",
         "autonomy": "suggest"} | (user["settings"] or {})
    from common.crypto import load_token
    return {"settings": s, "persona": user["persona"], "marketplace_mode": user["marketplace_mode"],
            "upwork_connected": bool(load_token(user["user_id"], "upwork")), "profile": prof}


@router.put("/settings")
def put_settings(body: SettingsIn, user=UserDep):
    s = dict(user["settings"] or {})
    for k in ("hourly_floor", "target_rate", "working_hours", "timezone", "autonomy"):
        v = getattr(body, k)
        if v is not None:
            s[k] = v
    db.x("UPDATE users SET settings=%s WHERE user_id=%s", (json.dumps(s), user["user_id"]))
    if body.persona and body.persona != user["persona"]:
        db.x("UPDATE users SET persona=%s WHERE user_id=%s", (body.persona, user["user_id"]))
        seed_searches(user["user_id"], body.persona)
    if body.marketplace_mode:
        db.x("UPDATE users SET marketplace_mode=%s WHERE user_id=%s", (body.marketplace_mode, user["user_id"]))
    return {"ok": True}


@router.get("/memory")
def memory(user=UserDep):
    from agent.memory.store import list_items
    cands = db.q("SELECT kind, key, occurrences, promoted, value FROM memory_candidates WHERE user_id=%s ORDER BY updated_at DESC", (user["user_id"],))
    return {"style": list_items(user["user_id"], "style"), "outcomes": list_items(user["user_id"], "outcomes"), "candidates": cands,
            "rules": settings.get("memory")}


@router.delete("/memory/{kind}/{key}")
def forget(kind: str, key: str, user=UserDep):
    from agent.memory.store import delete_item
    delete_item(user["user_id"], kind, key)
    db.x("UPDATE memory_candidates SET promoted=false, occurrences=0, edit_ids='{}' WHERE user_id=%s AND key=%s", (user["user_id"], key))
    return {"ok": True}


class OnboardIn(BaseModel):
    persona: str = Field(pattern="^(ai_ml_engineer|fullstack_web_dev|data_analyst)$")


@router.get("/personas")
def personas():
    out = []
    for p in ("ai_ml_engineer", "fullstack_web_dev", "data_analyst"):
        prof = json.loads((settings.ROOT / "data" / "personas" / p / "profile.json").read_text())
        out.append({"id": p, "name": prof["name"], "headline": prof["headline"], "summary": prof["summary"], "synthetic": True})
    return out


@router.post("/onboarding")
def onboard(body: OnboardIn, user=UserDep):
    db.x("UPDATE users SET persona=%s, onboarded=true WHERE user_id=%s", (body.persona, user["user_id"]))
    seed_searches(user["user_id"], body.persona)
    return {"ok": True}


ALLOWED = {".pdf", ".md", ".txt", ".json", ".jsonl", ".py", ".ts", ".js"}


@router.post("/portfolio/upload")
async def upload(files: list[UploadFile] = File(...), user=UserDep):
    """Own-profile mode: add files to the user's portfolio and re-index only that user's collection (incremental)."""
    base = _user_portfolio(user)
    saved = []
    for f in files[:20]:
        ext = Path(f.filename or "").suffix.lower()
        if ext not in ALLOWED:
            raise HTTPException(400, f"unsupported file type {ext}")
        sub = "case_studies" if ext in (".md", ".txt") else ("." if ext in (".pdf", ".json", ".jsonl") else "repos/uploaded/src")
        dest = base / sub / Path(f.filename).name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes((await f.read())[:2_000_000])
        saved.append(str(dest.relative_to(base)))
    s = dict(user["settings"] or {}, own_portfolio=True)
    db.x("UPDATE users SET settings=%s, onboarded=true WHERE user_id=%s", (json.dumps(s), user["user_id"]))
    return {"saved": saved, "reindex": "incremental: the next portfolio query re-indexes this user's collection (only new chunks are embedded)"}


def _user_portfolio(user: dict) -> Path:
    base = settings.ROOT / "data" / "user_portfolios" / user["user_id"]
    if not base.exists():
        shutil.copytree(settings.ROOT / "data" / "personas" / user["persona"], base)
    return base


class FromGithubIn(BaseModel):
    owner: str = Field(..., max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    repo: str = Field(..., max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    path: str = Field("", max_length=300)
    branch: str = Field("main", max_length=100)
    use_llm: bool = True


@router.post("/portfolio/from-github")
async def portfolio_from_github(body: FromGithubIn, user=UserDep):
    """X3: fetch a repo through the GitHub MCP server, draft a case study from it, verify every claim against the
    code, save the verified version into the user's portfolio (picked up by the next portfolio query)."""
    from agent.case_study_builder import build, save
    from rag.ingest.github_mcp import fetch_tree
    path = body.path.strip("/")
    name = path.rsplit("/", 1)[-1] if path else body.repo
    source = f"github-mcp://{body.owner}/{body.repo}/{path}"
    try:
        files = await fetch_tree(body.owner, body.repo, path, body.branch, max_files=60)
    except Exception as e:  # noqa: BLE001
        local = settings.ROOT / path
        own = (body.owner.lower(), body.repo.lower()) == ("talha-qamar", "agentic-a2") and path.startswith("data/personas/") and local.is_dir()
        if not own:
            raise HTTPException(502, f"GitHub MCP server unavailable: {str(e)[:200]}")
        files = {str(f.relative_to(local)): f.read_text(errors="ignore") for f in local.rglob("*") if f.is_file()}
        source = f"local-checkout (GitHub MCP unavailable: {type(e).__name__})"
    if not files:
        raise HTTPException(404, "no README or code files found at that path")
    try:
        r = await build(name, files, use_llm=body.use_llm, source=source)
    except Exception:  # noqa: BLE001 - model unavailable: deterministic draft, same verification
        r = await build(name, files, use_llm=False, source=source)
    p = save(r, _user_portfolio(user))
    s = dict(user["settings"] or {}, own_portfolio=True)
    db.x("UPDATE users SET settings=%s WHERE user_id=%s", (json.dumps(s), user["user_id"]))
    return {"saved": str(p.relative_to(_user_portfolio(user))), "source": source, "files_read": len(files), **{k: r[k] for k in ("title", "markdown", "draft", "verification", "checks", "skills")}}


@router.get("/portfolio/suggestions")
def portfolio_suggestions(user=UserDep):
    """X3: which case study to write next - gaps on skipped/watched jobs x hidden strengths in code."""
    from agent.portfolio_builder import suggest
    from mcp_servers.portfolio.backend import GigBidBackend
    jobs = [dict(r["summary"], job_id=r["job_id"], job=r["data"]) for r in
            db.q("SELECT job_id, data, summary FROM jobs WHERE user_id=%s AND summary IS NOT NULL ORDER BY created_at DESC LIMIT 200", (user["user_id"],))]
    s = user["settings"] or {}
    who = f"user:{user['user_id']}" if s.get("own_portfolio") else user["persona"]
    chunks = GigBidBackend(user["persona"]).retriever(who).corpus.chunks
    return {"jobs_considered": len(jobs), "suggestions": suggest(jobs, chunks, top=6)}


@router.get("/auth/upwork/start")
async def upwork_start(user=UserDep):
    import os

    from mcp_servers.marketplace.adapters.upwork_live import start_oauth
    redirect = os.environ.get("PUBLIC_URL", "http://localhost:8000").rstrip("/") + "/api/auth/upwork/callback"
    try:
        url = await start_oauth(user["user_id"], redirect)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"could not start Upwork OAuth: {e}") from e
    return {"authorize_url": url}


@router.get("/auth/upwork/callback")
def upwork_callback(code: str, state: str | None = None, user=UserDep):
    from mcp_servers.marketplace.adapters.upwork_live import finish_oauth
    ok = finish_oauth(user["user_id"], code, state)
    if ok:
        db.x("UPDATE users SET marketplace_mode='upwork_live' WHERE user_id=%s", (user["user_id"],))
    return {"connected": ok}
