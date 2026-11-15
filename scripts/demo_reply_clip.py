"""Record the client-reply scene on the live deployment and append it to the main demo video.

The reply was drafted by the conversation graph (intent -> liaison -> compliance) during the demo warm-up and is
waiting for approval; this records opening it, reading it and approving the send. No model call is made here.

    python scripts/demo_reply_clip.py --url https://gigbid-d3l2.onrender.com --base docs/demo/gigbid_demo.mp4 \
        --out runs/out/demo_full.mp4
"""
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from demo_video import CAPTION_JS, ffmpeg_bin, tts  # noqa: E402

NARRATION = ("A client replied with a question. The conversation graph read the intent, drafted a grounded answer with my rate "
             "floor and free slots, and ran compliance. Nothing is sent until I approve it here.")


async def record(url: str, email: str, password: str, work: Path, seconds: float) -> Path:
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": 1280, "height": 720}, record_video_dir=str(work), record_video_size={"width": 1280, "height": 720})
        page = await ctx.new_page()
        for _ in range(12):   # the free instance may be asleep: wake it before logging in
            try:
                if (await page.request.get(url + "/api/live", timeout=20000)).ok:
                    break
            except Exception:  # noqa: BLE001
                pass
            await page.wait_for_timeout(5000)
        r = await page.request.post(url + "/api/auth/login", data={"email": email, "password": password}, timeout=90000)
        assert r.ok, f"login failed: {r.status}"
        await page.goto(url + "/messages")
        await page.wait_for_timeout(2500)
        await page.evaluate(CAPTION_JS, "Client reply handled: intent, grounded draft, compliance, human approval")
        await page.get_by_test_id("reply-text").first.scroll_into_view_if_needed()
        await page.wait_for_timeout(int(max(4.0, seconds - 5) * 1000))
        btn = page.get_by_test_id("approve-reply").first
        if await btn.count():
            await btn.click()
        await page.wait_for_timeout(3500)
        await ctx.close()
        await b.close()
    return next(work.glob("*.webm"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--email", default=os.environ.get("REVIEWER_EMAIL"))
    ap.add_argument("--password", default=os.environ.get("REVIEWER_PASSWORD"))
    a = ap.parse_args()
    work = Path(tempfile.mkdtemp())
    wav = work / "reply.wav"
    secs = tts(NARRATION, wav)
    video = asyncio.run(record(a.url.rstrip("/"), a.email, a.password, work, secs))
    ff = ffmpeg_bin()
    clip = work / "clip.mp4"
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", str(video), "-i", str(wav), "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                    "-pix_fmt", "yuv420p", "-r", "25", "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2", "-shortest", str(clip)], check=True)
    subprocess.run([ff, "-y", "-loglevel", "error", "-i", a.base, "-i", str(clip), "-filter_complex",
                    "[0:v]fps=25,scale=1280:720,setsar=1[v0];[1:v]fps=25,scale=1280:720,setsar=1[v1];"
                    "[0:a]aresample=44100,aformat=channel_layouts=stereo[a0];[1:a]aresample=44100,aformat=channel_layouts=stereo[a1];"
                    "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "26", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", a.out], check=True)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
