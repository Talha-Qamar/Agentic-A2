"""Print each Groq model's remaining free-tier quota (one 1-token request per model; error body shows daily caps).

    python scripts/quota_probe.py
"""
import os

import httpx

MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
for m in MODELS:
    r = httpx.post("https://api.groq.com/openai/v1/chat/completions", timeout=30,
                   headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                   json={"model": m, "messages": [{"role": "user", "content": "ok"}], "max_tokens": 1})
    h = {k: v for k, v in r.headers.items() if k.startswith("x-ratelimit")}
    body = "" if r.status_code == 200 else r.text[:400]
    print(f"{m}: HTTP {r.status_code} {h} {body}", flush=True)
