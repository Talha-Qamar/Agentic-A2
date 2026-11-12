"""Print each Groq model's remaining free-tier quota (one 1-token request per model; error body shows daily caps).

    python scripts/quota_probe.py
"""
import os

import httpx

MODELS = ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
for m in (MODELS if os.environ.get("GROQ_API_KEY") else []):
    r = httpx.post("https://api.groq.com/openai/v1/chat/completions", timeout=30,
                   headers={"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"},
                   json={"model": m, "messages": [{"role": "user", "content": "ok"}], "max_tokens": 1})
    h = {k: v for k, v in r.headers.items() if k.startswith("x-ratelimit")}
    body = "" if r.status_code == 200 else r.text[:400]
    print(f"{m}: HTTP {r.status_code} {h} {body}", flush=True)
if os.environ.get("NVIDIA_API_KEY"):
    for m in ("openai/gpt-oss-20b", "openai/gpt-oss-120b"):
        r = httpx.post("https://integrate.api.nvidia.com/v1/chat/completions", timeout=60,
                       headers={"Authorization": f"Bearer {os.environ['NVIDIA_API_KEY']}"},
                       json={"model": m, "messages": [{"role": "user", "content": 'Reply with JSON {"ok": true}'}], "max_tokens": 64})
        print(f"nvidia {m}: HTTP {r.status_code} {r.text[:200]}", flush=True)
