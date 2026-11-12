"""R&D question C: does a multi-agent design beat a single agent here?

    python -m evals.runners.multiagent_comparison --limit 5      # jobs per persona

Same jobs, same models (config tier `strong` for the baselines), same MCP tools. Metrics per system:
bid/skip F1, unsupported-claim rate of the proposal (independent verifier: rag/verify.py against the portfolio),
LLM-judge quality (judge prompt; calibration in judge_calibration.json), latency, tokens, cost, and GigSim outcomes
(each system's proposals are submitted to its own GigSim account and the simulated clients react).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import httpx
from pydantic import BaseModel

from evals.runners.common import RowCache, load_dev, mean, pct, provenance, quota_exhausted, write_result
from evals.runners.decision_eval import f1, run_one

ADMIN = {"X-Admin-Key": os.environ.get("GIGSIM_ADMIN_KEY", "gigsim-admin")}
GS = os.environ.get("GIGSIM_URL", "http://localhost:8100")


class Judge(BaseModel):
    score: float
    reason: str = ""


async def judge(job: dict, letter: str) -> float | None:
    from agent.guardrails import wrap_untrusted
    from agent.llm import complete_json, load_prompt
    try:
        j = await complete_json("judge", load_prompt("judge"), f"JOB:\n{wrap_untrusted(job['title'] + chr(10) + job['description'][:2500])}\n\nPROPOSAL:\n{letter}",
                                Judge, max_tokens=300)
        return float(j.score)
    except Exception:  # noqa: BLE001
        return None


async def verify_letter(persona: str, letter: str) -> dict:
    """Independent grounding check of any system's proposal against the persona's portfolio (same verifier for all)."""
    from rag import verify as V
    from rag.embed import get_reranker
    from rag.retriever import get_retriever
    r = get_retriever(persona, "v2_hybrid")

    def search(q, k):
        return r.retrieve(q, requirements=[{"id": "q", "text": q}], k=k).items[:k]
    checks = V.verify_text(letter, search, get_reranker().score)
    return V.summary(checks)


def gigsim_account(system: str, persona: str) -> str:
    key = f"gs-key-cmp-{system}-{persona}"[:47]
    httpx.post(f"{GS}/v1/admin/accounts", json={"persona": persona, "api_key": key, "account_id": f"acct-{system[:6]}-{persona[:6]}"}, headers=ADMIN)
    return key


def submit_to_gigsim(key: str, job_id: str, letter: str, price: float | None, bid_type: str) -> str | None:
    """Evaluation only: submit the system's proposal straight to GigSim (no product approval flow) to observe clients."""
    H = {"X-GigSim-Key": key}
    letter = (letter or "")
    if len(letter) < 200:
        letter = letter + " " * (200 - len(letter))
    d = httpx.post(f"{GS}/v1/proposals/drafts", headers=H, json={"job_id": job_id, "cover_letter": letter[:4900], "bid_amount": float(price or 100),
                                                                   "bid_type": bid_type, "idempotency_key": f"cmp-{key[-12:]}-{job_id}"}).json()
    if "proposal_id" not in d:
        return None
    s = httpx.post(f"{GS}/v1/proposals/{d['proposal_id']}/submit", headers=H, json={"idempotency_key": f"cmps-{key[-12:]}-{job_id}"})
    return d["proposal_id"] if s.status_code == 200 else None


def outcomes(key: str) -> dict:
    httpx.post(f"{GS}/v1/admin/flush", headers=ADMIN)
    r = httpx.get(f"{GS}/v1/proposals", headers={"X-GigSim-Key": key})
    props = r.json().get("proposals", []) if r.status_code == 200 else []  # account never created = nothing submitted
    st = [p["status"] for p in props if p["status"] != "draft"]
    n = len(st)
    return {"submitted": n, "replied_or_better": sum(s in ("replied", "interview", "hired") for s in st),
            "reply_rate": round(sum(s in ("replied", "interview", "hired") for s in st) / n, 4) if n else None}


async def main_async(a) -> dict:
    from agent.graphs.baselines import clean_decision, run_single_react, run_supervisor
    from agent.mcp_client import load_tools
    from common.tokens import mint_mcp_token
    jobs = load_dev(limit_per_persona=a.limit)
    cache = RowCache(a.out.removesuffix(".json"))
    rows, stopped = [], None
    for j in jobs:
        if stopped:
            break
        user = {"user_id": f"cmp-{j['persona']}", "persona": j["persona"], "gigsim_key": f"gs-key-{j['persona']}"}
        tools = await load_tools(user["user_id"], mint_mcp_token(user["user_id"], j["persona"], user["gigsim_key"]))
        for system in a.systems.split(","):
            key = f"{system}{a.tag}:{j['job_id']}"
            if cache.get(key):
                rows.append(cache.get(key))
                continue
            try:
                if system == "gigbid_graph":
                    r = await run_one(j, user, None)
                    err = r.get("error") or (r.get("errors") if r.get("status") in ("dead_letter", "needs_attention") else None)
                    res = {"decision": r["pred"], "cover_letter": r.get("cover_letter"), "price": r.get("price"), "latency_s": r["latency_s"],
                           "tokens": r.get("tokens", 0), "cost_usd": r.get("cost_usd", 0.0), "tool_calls": None,
                           "error": json.dumps(err)[:300] if err else None}
                elif system == "single_react":
                    res = await run_single_react(tools, j["job_id"])
                else:
                    res = await run_supervisor(tools, j["job_id"])
            except Exception as e:  # noqa: BLE001
                res = {"decision": "skip", "error": f"{type(e).__name__}: {str(e)[:500]}", "latency_s": 0, "tokens": 0, "cost_usd": 0}
            if quota_exhausted(res.get("error")):
                stopped = f"daily quota reached at {key}: {str(res.get('error'))[:160]}"
                print("STOP:", stopped, flush=True)
                break
            dec = clean_decision(res.get("decision"))
            letter = res.get("cover_letter") if dec == "bid" else None
            row = {"system": system, "job_id": j["job_id"], "persona": j["persona"], "gold": j["labels"]["gold_decision"], "pred": dec,
                   "latency_s": res.get("latency_s"), "tokens": res.get("tokens"), "cost_usd": res.get("cost_usd"), "tool_calls": res.get("tool_calls"),
                   "error": res.get("error"), "has_letter": bool(letter)}
            if letter:
                row["verify"] = await verify_letter(j["persona"], letter)
                row["judge"] = await judge(j, letter)
                row["letter"] = letter
                key = gigsim_account(system + a.tag, j["persona"])
                row["gigsim_proposal"] = submit_to_gigsim(key, j["job_id"], letter, res.get("price"), j["budget_type"])
            print(f"[{system}] {j['job_id']} gold={row['gold']} pred={dec} judge={row.get('judge')} uns={row.get('verify', {}).get('unsupported_rate')} "
                  f"{row['latency_s']}s ${row['cost_usd']} {row.get('error') or ''}", flush=True)
            if row["has_letter"] and row.get("judge") is None and quota_exhausted(str(row.get("verify"))):
                stopped = f"daily quota reached while judging {key}"
                break
            cache.put(key, row)
            rows.append(row)
    summary = {}
    for system in a.systems.split(","):
        rs = [r for r in rows if r["system"] == system]
        tp = sum(r["pred"] == "bid" and r["gold"] == "bid" for r in rs)
        fp = sum(r["pred"] == "bid" and r["gold"] != "bid" for r in rs)
        fn = sum(r["pred"] != "bid" and r["gold"] == "bid" for r in rs)
        letters = [r for r in rs if r.get("verify")]
        cl = sum(r["verify"]["claims"] for r in letters)
        un = sum(r["verify"]["unsupported"] for r in letters)
        persona_keys = {f"gs-key-cmp-{system + a.tag}-{p}"[:47] for p in {r["persona"] for r in rs}}
        oc = [outcomes(k) for k in persona_keys]
        sub = sum(o["submitted"] for o in oc)
        rep = sum(o["replied_or_better"] for o in oc)
        summary[system] = {"n": len(rs), "errors": sum(bool(r["error"]) for r in rs), "bid_f1": round(f1(tp, fp, fn), 4),
                           "proposals": len(letters), "unsupported_claim_rate": round(un / cl, 4) if cl else None,
                           "judge_mean": round(mean([r["judge"] for r in letters if r.get("judge") is not None]), 2) if letters else None,
                           "p95_latency_s": round(pct([r["latency_s"] or 0 for r in rs], 95), 2), "mean_cost_usd": round(mean([r["cost_usd"] or 0 for r in rs]), 6),
                           "mean_tokens": round(mean([r["tokens"] or 0 for r in rs]), 1), "gigsim_submitted": sub,
                           "gigsim_reply_rate": round(rep / sub, 4) if sub else None}
    return {"summary": summary, "rows": rows, "complete": not stopped, "stopped": stopped,
            "planned_rows": len(jobs) * len(a.systems.split(","))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--systems", default="gigbid_graph,single_react,supervisor")
    ap.add_argument("--out", default="multiagent_comparison.json")
    ap.add_argument("--tag", default="", help="suffix for GigSim accounts, e.g. a retrieval-variant run on the same jobs")
    a = ap.parse_args()
    sys.path.insert(0, "scripts")
    import run_stack
    ps = run_stack.start({"GIGSIM_ERROR_RATE": "0.02", "GIGSIM_DB": "var/cmp_gigsim.db"})
    try:
        res = asyncio.run(main_async(a))
    finally:
        run_stack.stop(ps)
    from agent import settings
    write_result(a.out, {"provenance": provenance({"profile": settings.get("profile"), "baseline_model": settings.model_for("baseline_agent"),
                                                     "rag_variant": settings.get("rag.variant"), "tag": a.tag}), **res})
    print(json.dumps(res["summary"], indent=1))


if __name__ == "__main__":
    main()
