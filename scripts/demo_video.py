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

CAPTION_JS = """(t) => { let d = document.getElementById('__cap'); if (!d) { d = document.createElement('div'); d.id='__cap';
 d.style.cssText='position:fixed;left:50%;bottom:18px;transform:translateX(-50%);max-width:86%;background:rgba(15,23,42,.88);color:#fff;'+
 'font:600 17px/1.4 Inter,system-ui,sans-serif;padding:10px 16px;border-radius:10px;z-index:99999;box-shadow:0 6px 24px rgba(0,0,0,.25)';
 document.body.appendChild(d);} d.textContent = t; }"""

# (narration, caption) per scene; actions live in run_scene()
SCENES = [
    ("GigBid is a team of AI agents for freelancers. It scouts jobs, checks fit and risk, writes proposals grounded in your real portfolio, and never sends anything without your approval.",
     "GigBid: a multi-agent freelancer copilot (LangGraph + MCP, open models)"),
    ("I sign in as the reviewer. The persona is a synthetic AI engineer whose portfolio has case studies, repositories, reviews and past proposals with outcomes.",
     "Sign in - synthetic persona with a messy, realistic portfolio"),
    ("The marketplace here is GigSim, our simulator. I advance its clock so new jobs are posted, and run the scout. Each job is analysed by parallel agents: job analyst, risk assessor and fit matcher.",
     "Scout + parallel analysis: analyst, risk, matcher (LangGraph Send fan-out)"),
    ("The inbox shows the decision, fit, risk, suggested price and the reason. Scams and reposts are caught: this one asks for payment outside the platform, so it is skipped.",
     "Inbox: decisions with reasons - scams skipped, reposts deduplicated"),
    ("For a strong match, the job page maps every requirement to portfolio evidence, lists risk flags, and explains the price from real Upwork market data and the Connects cost.",
     "Requirement-by-requirement evidence, risk flags, price rationale"),
    ("The proposal studio shows the exact text that would be sent. Every claim was checked against the portfolio, and unsupported claims were removed before the critic reviewed the draft. The compliance guard added the disclosure required by the November policy update.",
     "Proposal studio: verified claims, critic, compliance, exact dry-run preview"),
    ("I edit a sentence. The edit goes back through compliance and the marketplace dry run, and GigBid asks again. Edits also feed style memory, which only promotes a rule after it repeats.",
     "Human edit -> re-check -> new preview (interrupt + resume)"),
    ("Now I approve. Only this click mints the approval token the marketplace server requires to spend Connects, and the submit reuses the preview's idempotency key, so it can never be sent twice.",
     "Approve -> exactly-once submit with a human-minted approval token"),
    ("On the pipeline, time passes and the simulated client replies. The client liaison drafts an answer grounded in the portfolio, which again waits for my approval.",
     "Pipeline + client conversation with suggested, approvable replies"),
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
        skip = await page.query_selector("text=skip")
        if skip:
            await skip.scroll_into_view_if_needed()
        await hold(3, t0)
        # 4 job detail of a bid
        t0 = time.monotonic(); await cap(4)
        rows = await (await api.get(url + "/api/jobs")).json()
        target = next((r for r in rows if r.get("action") == "bid"), rows[0] if rows else None)
        if target:
            await page.goto(f"{url}/jobs/{target['job_id']}")
            await page.wait_for_timeout(1500); await cap(4)
            await page.mouse.wheel(0, 500)
        await hold(4, t0)
        # 5 studio
        t0 = time.monotonic(); await cap(5)
        appr = []
        for _ in range(60):
            appr = await (await api.get(url + "/api/approvals")).json()
            if appr:
                break
            await page.wait_for_timeout(4000)
        if appr:
            await page.goto(f"{url}/studio/{appr[0]['thread_id']}")
            await page.wait_for_timeout(1500); await cap(5)
            await page.mouse.wheel(0, 300)
        await hold(5, t0)
        # 6 edit
        t0 = time.monotonic(); await cap(6)
        if appr:
            box = page.get_by_test_id("draft-text")
            await box.click()
            await page.keyboard.press("End")
            await page.keyboard.type("\n\nHappy to walk you through a similar repository on a short call.", delay=12)
            await page.get_by_test_id("save-edit").click()
            for _ in range(40):
                a2 = await (await api.get(url + "/api/approvals")).json()
                if a2 and a2[0]["approval_id"] != appr[0]["approval_id"]:
                    appr = a2
                    break
                await page.wait_for_timeout(3000)
            await page.reload(); await cap(6)
        await hold(6, t0)
        # 7 approve
        t0 = time.monotonic(); await cap(7)
        if appr:
            await page.get_by_test_id("approve").click()
            await page.wait_for_timeout(2500); await cap(7)
        await hold(7, t0)
        # 8 pipeline + messages
        t0 = time.monotonic(); await cap(8)
        await page.goto(url + "/pipeline"); await cap(8)
        await page.get_by_test_id("advance-sync").click()
        await page.wait_for_timeout(6000)
        await page.goto(url + "/messages"); await cap(8)
        await hold(8, t0)
        # 9 degraded
        t0 = time.monotonic(); await cap(9)
        await api.post(url + "/api/demo/fault", data={"down": True})
        await page.goto(url + "/inbox"); await page.wait_for_timeout(2500); await cap(9)
        await api.post(url + "/api/demo/fault", data={"down": False})
        await hold(9, t0)
        # 10 trace
        t0 = time.monotonic(); await cap(10)
        runs = await (await api.get(url + "/api/runs")).json()
        if runs:
            await page.goto(f"{url}/runs/{runs[0]['thread_id']}"); await page.wait_for_timeout(1200); await cap(10)
        await hold(10, t0)
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


def prepare(url: str, email: str, password: str, timeout_s: int = 600) -> None:
    """Unrecorded warm-up: wake the instance, scout, and wait until analysed jobs and one pending approval exist."""
    import httpx
    c = httpx.Client(base_url=url, timeout=120)
    for _ in range(30):
        try:
            if c.get("/api/health").status_code == 200:
                break
        except Exception:  # noqa: BLE001 - free instance waking up
            time.sleep(10)
    c.post("/api/auth/login", json={"email": email, "password": password}).raise_for_status()
    c.post("/api/demo/advance", json={"minutes": 240})
    c.post("/api/scout/run")
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        jobs = c.get("/api/jobs").json()
        appr = c.get("/api/approvals").json()
        print(f"prep: {sum(1 for j in jobs if j.get('action'))} analysed, {len(appr)} approvals", flush=True)
        if sum(1 for j in jobs if j.get("action")) >= 3 and appr:
            return
        time.sleep(15)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", required=True)
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


if __name__ == "__main__":
    sys.exit(main())
