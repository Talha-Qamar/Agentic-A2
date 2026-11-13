"""Record the 3-minute demo video: Playwright drives the real web app, captions are overlaid, narration is synthesised
(macOS `say`, or espeak-ng on Linux) and muxed with ffmpeg (imageio-ffmpeg binary).

    python scripts/demo_video.py --url https://<app> --email <reviewer> --password <pw> --out var/demo/gigbid_demo.mp4

The app is used for real (open profile, live LLM calls); nothing in the video is mocked.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

import httpx

CAPTION_JS = """(t) => { let d = document.getElementById('__cap'); if (!d) { d = document.createElement('div'); d.id='__cap';
 d.style.cssText='position:fixed;left:50%;bottom:18px;transform:translateX(-50%);max-width:86%;background:rgba(15,23,42,.88);color:#fff;'+
 'font:600 17px/1.4 Inter,system-ui,sans-serif;padding:10px 16px;border-radius:10px;z-index:99999;box-shadow:0 6px 24px rgba(0,0,0,.25)';
 document.body.appendChild(d);} d.textContent = t; }"""

# illustrative dev-pool jobs: an off-platform-payment scam and a post with a planted "ignore your criteria and bid" line
SCAM_JOB = os.environ.get("DEMO_SCAM_JOB", "dev-922f47037a")
INJECTION_JOB = os.environ.get("DEMO_INJECTION_JOB", "dev-19cf56c7ca")
PUBLISH: list[str] = []   # threads whose traces are made public after recording

# (narration, caption) per scene; actions live in record()
SCENES = [
    ("GigBid is a team of AI agents for freelancers. It scouts jobs, checks fit and risk, writes proposals grounded in your real portfolio, and never sends anything without your approval.",
     "GigBid: a multi-agent freelancer copilot (LangGraph + MCP, open models)"),
    ("I sign in as the reviewer. The persona is a synthetic AI engineer whose portfolio has case studies, repositories, reviews and past proposals with outcomes.",
     "Sign in - synthetic persona with a messy, realistic portfolio"),
    ("The marketplace here is GigSim, our simulator. I advance its clock so new jobs are posted, and run the scout. Each job is analysed by parallel agents: job analyst, risk assessor and fit matcher.",
     "Scout + parallel analysis: analyst, risk, matcher (LangGraph Send fan-out)"),
    ("The inbox shows the decision, fit, risk, suggested price and the reason for every job. This one asks to be paid outside the platform. The risk assessor flags it as a scam and GigBid skips it without writing a word.",
     "Scam caught: off-platform payment -> skipped, no proposal drafted"),
    ("For a strong match, the job page maps every requirement to portfolio evidence, lists risk flags, and explains the price from real Upwork market data and the Connects cost.",
     "Requirement-by-requirement evidence, risk flags, price rationale"),
    ("This post hides an instruction telling the AI to ignore its criteria and always bid. The text is quarantined before any model reads it, and the decision is a rule over evidence scores, so the instruction changes nothing: the job is skipped on fit.",
     "Injected instruction ignored: quarantined, decision made by rules on evidence"),
    ("The proposal studio shows the exact text that would be sent. Every claim was checked against the portfolio, and unsupported claims were removed before the critic reviewed the draft. The compliance guard added the disclosure required by the November policy update.",
     "Proposal studio: verified claims, critic, compliance, exact dry-run preview"),
    ("I edit a sentence. The edit goes back through compliance and the marketplace dry run, and GigBid asks again. Edits also feed style memory, which only promotes a rule after it repeats.",
     "Human edit -> re-check -> new preview (interrupt + resume)"),
    ("Now I approve. Only this click mints the approval token the marketplace server requires to spend Connects, and the submit reuses the preview's idempotency key, so it can never be sent twice.",
     "Approve -> exactly-once submit with a human-minted approval token"),
    ("On the pipeline, time passes and the simulated client replies. The client liaison classifies the message, drafts an answer grounded in the portfolio, and waits for my approval before sending.",
     "Client reply handled: intent, grounded draft, approve and send"),
    ("If the marketplace goes down, GigBid switches to degraded mode with a clear banner and queues work instead of failing.",
     "Degraded mode when the marketplace is unavailable"),
    ("Every run is traced: each node, tool call, token count and cost. Retrieval, decisions, the multi-agent comparison and the injection tests are all measured in the evaluation suite in the repository. Thanks for watching.",
     "Run trace: per-node tokens and cost - all results in evals/results"),
]


def tts(text: str, out_wav: Path) -> float:
    ff = ffmpeg_bin()
    if shutil.which("say"):
        aiff = out_wav.with_suffix(".aiff")
        subprocess.run(["say", "-v", os.environ.get("VOICE", "Samantha"), "-r", "182", "-o", str(aiff), text], check=True)
        subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(aiff), "-ar", "44100", "-ac", "1", str(out_wav)], check=True)
    elif shutil.which("espeak-ng"):
        subprocess.run(["espeak-ng", "-s", "165", "-w", str(out_wav), text], check=True)
    else:
        raise SystemExit("no TTS engine (say / espeak-ng)")
    with wave.open(str(out_wav)) as w:
        return w.getnframes() / w.getframerate()


def ffmpeg_bin() -> str:
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


async def record(url: str, email: str, password: str, workdir: Path, durations: list[float]) -> Path:
    from playwright.async_api import async_playwright
    timeline = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        ctx = await browser.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(workdir), record_video_size={"width": 1280, "height": 720})
        page = await ctx.new_page()
        t_start = time.monotonic()
        api = page.request

        async def cap(i):
            await page.evaluate(CAPTION_JS, SCENES[i][1])
            timeline.append((i, time.monotonic() - t_start))

        async def hold(i, t0):
            rest = durations[i] + 0.6 - (time.monotonic() - t0)
            if rest > 0:
                await page.wait_for_timeout(int(rest * 1000))

        # 0 intro on login page
        await page.goto(url + "/login")
        t0 = time.monotonic(); await cap(0); await hold(0, t0)
        # 1 sign in
        t0 = time.monotonic(); await cap(1)
        await page.get_by_test_id("email").fill(email)
        await page.get_by_test_id("password").fill(password)
        await page.get_by_test_id("login-submit").click()
        await page.wait_for_url("**/inbox")
        await cap(1); await hold(1, t0)
        # 2 scout
        t0 = time.monotonic(); await cap(2)
        await page.get_by_test_id("advance").click()
        await page.get_by_test_id("scout-now").click()
        await page.wait_for_timeout(2000); await cap(2)
        await hold(2, t0)
        # 3 inbox - wait for analysed rows
        t0 = time.monotonic(); await cap(3)
        for _ in range(60):
            rows = await (await api.get(url + "/api/jobs")).json()
            if sum(1 for r in rows if r.get("action")) >= 3:
                break
            await page.wait_for_timeout(4000)
        await page.reload(); await cap(3)
        await page.wait_for_timeout(2500)
        await page.goto(f"{url}/jobs/{SCAM_JOB}"); await page.wait_for_timeout(1500); await cap(3)
        await hold(3, t0)
        # 4 job detail of a bid
        t0 = time.monotonic(); await cap(4)
        rows = await (await api.get(url + "/api/jobs")).json()
        target = next((r for r in rows if r.get("action") == "bid" and r["job_id"] not in (SCAM_JOB, INJECTION_JOB)), rows[0] if rows else None)
        if target:
            await page.goto(f"{url}/jobs/{target['job_id']}")
            await page.wait_for_timeout(1500); await cap(4)
            await page.mouse.wheel(0, 500)
        await hold(4, t0)
        # 5 injected instruction ignored
        t0 = time.monotonic(); await cap(5)
        await page.goto(f"{url}/jobs/{INJECTION_JOB}")
        await page.wait_for_timeout(1500); await cap(5)
        inj = await page.query_selector("text=Prompt injection detected")
        if inj:
            await inj.scroll_into_view_if_needed()
        await hold(5, t0)
        # 6 studio
        t0 = time.monotonic(); await cap(6)
        appr = []
        for _ in range(60):
            appr = [a for a in await (await api.get(url + "/api/approvals")).json() if a["kind"] == "proposal_approval"]
            if appr:
                break
            await page.wait_for_timeout(4000)
        if appr:
            await page.goto(f"{url}/studio/{appr[0]['thread_id']}")
            await page.wait_for_timeout(1500); await cap(6)
            await page.mouse.wheel(0, 300)
        await hold(6, t0)
        # 7 edit
        t0 = time.monotonic(); await cap(7)
        if appr:
            box = page.get_by_test_id("draft-text")
            await box.click()
            await page.keyboard.press("End")
            await page.keyboard.type("\n\nHappy to walk you through a similar repository on a short call.", delay=12)
            await page.get_by_test_id("save-edit").click()
            for _ in range(40):
                a2 = [a for a in await (await api.get(url + "/api/approvals")).json() if a["kind"] == "proposal_approval"]
                if a2 and a2[0]["approval_id"] != appr[0]["approval_id"]:
                    appr = a2
                    break
                await page.wait_for_timeout(3000)
            await page.reload(); await cap(7)
        await hold(7, t0)
        # 8 approve
        t0 = time.monotonic(); await cap(8)
        if appr:
            PUBLISH.append(appr[0]["thread_id"])
            await page.get_by_test_id("approve").click()
            await page.wait_for_timeout(2500); await cap(8)
        await hold(8, t0)
        # 9 pipeline + client reply
        t0 = time.monotonic(); await cap(9)
        await page.goto(url + "/pipeline"); await cap(9)
        await page.get_by_test_id("advance-sync").click()
        for _ in range(4):
            ra = [a for a in await (await api.get(url + "/api/approvals")).json() if a["kind"] != "proposal_approval"]
            if ra:
                break
            await page.wait_for_timeout(2500)
        await page.goto(url + "/messages"); await page.wait_for_timeout(1500); await cap(9)
        btn = await page.query_selector("[data-testid=approve-reply]")
        if btn:
            await btn.scroll_into_view_if_needed()
            await page.wait_for_timeout(1500)
            await btn.click()
            await page.wait_for_timeout(2000)
        await hold(9, t0)
        # 10 degraded
        t0 = time.monotonic(); await cap(10)
        await api.post(url + "/api/demo/fault", data={"down": True})
        try:
            await page.goto(url + "/inbox"); await page.wait_for_timeout(2500); await cap(10)
        finally:   # never leave the live deployment in degraded mode
            await api.post(url + "/api/demo/fault", data={"down": False})
        await hold(10, t0)
        # 11 trace
        t0 = time.monotonic(); await cap(11)
        if PUBLISH:
            await page.goto(f"{url}/runs/{PUBLISH[0]}"); await page.wait_for_timeout(1200); await cap(11)
        await hold(11, t0)
        await page.wait_for_timeout(800)
        await ctx.close()
        await browser.close()
    vids = sorted(workdir.glob("*.webm"), key=lambda p: p.stat().st_mtime)
    (workdir / "timeline.txt").write_text("\n".join(f"{i} {t:.2f}" for i, t in timeline))
    return vids[-1]


def build_audio(workdir: Path, wavs: list[Path], starts: dict[int, float]) -> Path:
    ff = ffmpeg_bin()
    inputs, filters = [], []
    for i, w in enumerate(wavs):
        inputs += ["-i", str(w)]
        ms = int(starts.get(i, 0) * 1000)
        filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(len(wavs))) + f"amix=inputs={len(wavs)}:normalize=0[out]"
    out = workdir / "narration.wav"
    subprocess.run([ff, "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters) + ";" + mix, "-map", "[out]", str(out)], check=True)
    return out


class _RetryClient(httpx.Client):
    """The free instance can restart or answer 502 for a moment; retry instead of failing the recording."""

    def request(self, *a, **kw):
        for i in range(6):
            r = super().request(*a, **kw)
            if r.status_code < 500 and (r.headers.get("content-type", "").startswith("application/json") or r.request.method != "GET"):
                return r
            time.sleep(10 * (i + 1))
        return r


def prepare(url: str, email: str, password: str, timeout_s: int = 600) -> None:
    """Unrecorded warm-up: wake the instance, scout, and wait until analysed jobs and one pending approval exist."""
    c = _RetryClient(base_url=url, timeout=120)
    for _ in range(30):
        try:
            if c.get("/api/health").status_code == 200:
                break
        except Exception:  # noqa: BLE001 - free instance waking up
            time.sleep(10)
    c.post("/api/auth/login", json={"email": email, "password": password}).raise_for_status()
    c.post("/api/demo/fault", json={"down": False})   # clear a degraded state left by an interrupted earlier recording
    c.post("/api/demo/advance", json={"minutes": 240})
    c.post("/api/scout/run")
    for jid in (SCAM_JOB, INJECTION_JOB):
        c.post("/api/jobs", json={"job_id": jid})
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        jobs = c.get("/api/jobs").json()
        appr = [a for a in c.get("/api/approvals").json() if a["kind"] == "proposal_approval"]
        done = {j["job_id"] for j in jobs if j.get("action")}
        print(f"prep: {len(done)} analysed, {len(appr)} approvals", flush=True)
        if len(done) >= 3 and len(appr) >= 2 and {SCAM_JOB, INJECTION_JOB} <= done:
            break
        time.sleep(15)
    # unrecorded: approve one proposal and let simulated time pass until a client reply is waiting for approval,
    # so the recorded "client reply handled" scene does not have to wait for the simulator
    for _ in range(int(os.environ.get("PREP_REPLY_ROUNDS", "8"))):
        replies = [a for a in c.get("/api/approvals").json() if a["kind"] == "message_approval"]
        if replies:
            print("prep: client reply waiting for approval", flush=True)
            return
        appr = [a for a in c.get("/api/approvals").json() if a["kind"] == "proposal_approval"]
        for a in appr[1:]:            # keep the newest proposal pending for the recorded studio scene
            c.post(f"/api/approvals/{a['approval_id']}", json={"action": "approve"})
        if len(appr) <= 1:            # need more proposals: scout again
            c.post("/api/scout/run")
        time.sleep(20)
        c.post("/api/demo/advance", json={"minutes": 600})
        c.post("/api/pipeline/sync")
        time.sleep(45)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--email", default=os.environ.get("REVIEWER_EMAIL"))
    ap.add_argument("--password", default=os.environ.get("REVIEWER_PASSWORD"))
    ap.add_argument("--out", default="var/demo/gigbid_demo.mp4")
    a = ap.parse_args()
    work = Path(a.out).parent / "work"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    wavs, durs = [], []
    for i, (narr, _) in enumerate(SCENES):
        w = work / f"n{i:02d}.wav"
        durs.append(tts(narr, w))
        wavs.append(w)
    print("narration seconds:", round(sum(durs), 1))
    if not os.environ.get("SKIP_PREP"):
        prepare(a.url.rstrip("/"), a.email, a.password)
    video = asyncio.run(record(a.url.rstrip("/"), a.email, a.password, work, durs))
    first = {}
    for line in (work / "timeline.txt").read_text().splitlines():
        i, t = line.split()
        first.setdefault(int(i), float(t))
    audio = build_audio(work, wavs, first)
    ff = ffmpeg_bin()
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(video), "-i", str(audio), "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", a.out], check=True)
    print("wrote", a.out)
    publish_traces(a.url.rstrip("/"), a.email, a.password, Path(a.out).parent / "public_traces.json")


def publish_traces(url: str, email: str, password: str, out: Path) -> None:
    """Make three runs public (approved proposal, scam skipped, injection ignored) and record their links."""
    import json

    import httpx
    c = httpx.Client(base_url=url, timeout=60)
    c.post("/api/auth/login", json={"email": email, "password": password}).raise_for_status()
    jobs = {j["job_id"]: j for j in c.get("/api/jobs").json()}
    picks = {"approved_proposal": PUBLISH[0] if PUBLISH else None,
             "scam_skipped": (jobs.get(SCAM_JOB) or {}).get("thread_id"),
             "injection_ignored": (jobs.get(INJECTION_JOB) or {}).get("thread_id")}
    links = {}
    for k, tid in picks.items():
        if tid:
            c.post(f"/api/runs/{tid}/public", json={"public": True}).raise_for_status()
            links[k] = f"{url}/t/{tid}"
    out.write_text(json.dumps(links, indent=1))
    print("public traces:", links)


if __name__ == "__main__":
    sys.exit(main())
