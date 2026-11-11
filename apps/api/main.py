"""GigBid API (FastAPI).

    uvicorn apps.api.main:app --port 8000                 # docker compose: GigSim, MCP servers, worker run separately
    GIGBID_ALLINONE=1 uvicorn apps.api.main:app            # Render free tier: one process mounts GigSim at /gigsim,
                                                            # the MCP servers at /mcp/<name>/mcp and runs the Arq worker
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent import settings
from apps.api.auth.session import create_user, seed_searches
from apps.api.routers import approvals, auth, jobs, runs, workspace
from common import db

log = logging.getLogger("gigbid.api")
ALLINONE = os.environ.get("GIGBID_ALLINONE") == "1"
WEB_DIST = settings.ROOT / "apps" / "web" / "dist"


def seed_users() -> None:
    """Reviewer + demo accounts. Credentials come from env (never committed)."""
    email = os.environ.get("REVIEWER_EMAIL", "reviewer@gigbid.local")
    pw = os.environ.get("REVIEWER_PASSWORD", "reviewer-local-only")
    if not db.one("SELECT 1 FROM users WHERE email=%s", (email.lower(),)):
        u = create_user(email, pw, "Reviewer", persona=os.environ.get("REVIEWER_PERSONA", "ai_ml_engineer"), onboarded=True)
        log.info("seeded reviewer %s", u["user_id"])
    for p in ("fullstack_web_dev", "data_analyst"):
        e = f"demo-{p}@gigbid.local"
        if not db.one("SELECT 1 FROM users WHERE email=%s", (e,)):
            create_user(e, pw, f"Demo {p}", persona=p, onboarded=True)


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with contextlib.AsyncExitStack() as stack:
        db.init_schema()
        if ALLINONE:
            from gigsim.app import store as gstore
            if not gstore.seeded():
                gstore.seed()
            for m in app.state.mcp_servers:
                await stack.enter_async_context(m.session_manager.run())
        try:
            seed_users()
        except Exception as e:  # noqa: BLE001
            log.error("seeding users failed: %s", e)
        from agent.tracing import setup_tracing
        setup_tracing("gigbid-api")
        bg = []
        if ALLINONE and os.environ.get("ALLINONE_WORKER", "1") == "1":
            bg.append(asyncio.create_task(_worker_loop()))
        yield
        for t in bg:
            t.cancel()


async def _worker_loop():
    """Single-process deployments: Arq worker on Redis if REDIS_URL is set, otherwise a periodic in-process ticker."""
    await asyncio.sleep(5)
    if os.environ.get("REDIS_URL"):
        from arq.worker import Worker
        from worker.main import WorkerSettings
        w = Worker(functions=WorkerSettings.functions, cron_jobs=WorkerSettings.cron_jobs, redis_settings=WorkerSettings.redis_settings,
                   max_jobs=2, job_timeout=900, handle_signals=False)
        await w.async_run()
    else:
        from worker.tasks import tick
        while True:
            try:
                await tick({})
            except Exception as e:  # noqa: BLE001
                log.warning("tick failed: %s", e)
            await asyncio.sleep(int(os.environ.get("TICK_MINUTES", "5")) * 60)


def create_app() -> FastAPI:
    app = FastAPI(title="GigBid API", version="1.0.0", lifespan=lifespan,
                  description="Multi-agent freelancer copilot. All marketplace writes require human approval.")
    for r in (auth.router, jobs.router, runs.router, approvals.router, workspace.router):
        app.include_router(r)
    app.state.mcp_servers = []
    if ALLINONE:
        from gigsim.app import app as gigsim_app
        from mcp_servers.marketplace.server import build_server as mk
        from mcp_servers.portfolio.server import build_server as pf
        from mcp_servers.workspace.server import build_server as ws
        app.mount("/gigsim", gigsim_app)
        for name, builder in (("portfolio", pf), ("marketplace", mk), ("workspace", ws)):
            m = builder()
            app.state.mcp_servers.append(m)
            app.mount(f"/mcp/{name}", m.streamable_http_app())

    @app.get("/api/health")
    async def health():
        out = {"api": "ok", "db": "ok", "marketplace": "ok", "degraded": False, "profile": settings.get("profile"),
               "rag_variant": settings.get("rag.variant"), "allinone": ALLINONE}
        try:
            db.q("SELECT 1")
        except Exception as e:  # noqa: BLE001
            out.update(db=f"down: {e}", degraded=True)
        try:
            async with httpx.AsyncClient(timeout=3) as c:
                r = await c.get(settings.get("marketplace.gigsim_url").rstrip("/") + "/health")
                g = r.json()
                if r.status_code != 200 or g.get("down"):
                    raise RuntimeError(g)
                out["gigsim"] = g
        except Exception as e:  # noqa: BLE001
            out.update(marketplace=f"unavailable: {str(e)[:120]}", degraded=True)
        return out

    class FaultIn(BaseModel):
        down: bool

    @app.post("/api/demo/fault")
    async def demo_fault(body: FaultIn):
        """Demo control: take GigSim down/up to show degraded mode (marketplace admin key held server-side)."""
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.post(settings.get("marketplace.gigsim_url").rstrip("/") + "/v1/admin/fault", json={"down": body.down},
                             headers={"X-Admin-Key": os.environ.get("GIGSIM_ADMIN_KEY", "gigsim-admin")})
        return r.json()

    class AdvanceIn(BaseModel):
        minutes: float = 120

    @app.post("/api/demo/advance")
    async def demo_advance(body: AdvanceIn):
        """Demo control: advance the simulated marketplace clock (new jobs appear, clients react)."""
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(settings.get("marketplace.gigsim_url").rstrip("/") + "/v1/admin/advance", json={"minutes": min(body.minutes, 2880)},
                             headers={"X-Admin-Key": os.environ.get("GIGSIM_ADMIN_KEY", "gigsim-admin")})
        return r.json()

    if WEB_DIST.exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def spa(path: str, request: Request):
            if path.startswith(("api/", "gigsim", "mcp/")):
                return JSONResponse({"detail": "not found"}, status_code=404)
            f = WEB_DIST / path
            if path and f.is_file():
                return FileResponse(f)
            return FileResponse(WEB_DIST / "index.html")
    return app


app = create_app()
seed_searches  # noqa: B018
Path  # noqa: B018
