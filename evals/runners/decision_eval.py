"""End-to-end decision evaluation of the GigBid graph against GigSim (dev set or hidden-test seed).

    python -m evals.runners.decision_eval --limit 20 --out decision_eval.json
    python -m evals.runners.decision_eval --limit 10 --out smoke_eval.json --gate     # CI gate (fails on regression)

For each job: runs the real bid graph (MCP servers + GigSim must be up; scripts/run_stack.py is started automatically)
and records decision, scam score, price vs fair band, unsupported claims before/after verification, latency, tokens,
cost.  Stops at the approval interrupt (no proposals are submitted).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time

from evals.runners.common import RESULTS, load_dev, mean, pct, provenance, write_result

GATES = {"bid_f1_min": 0.55, "unsupported_after_max": 0.10}


def f1(tp: int, fp: int, fn: int) -> float:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return 2 * p * r / (p + r) if p + r else 0.0


def score(rows: list[dict]) -> dict:
    ok = [r for r in rows if not r.get("error")]
    tp = sum(r["pred"] == "bid" and r["gold"] == "bid" for r in ok)
    fp = sum(r["pred"] == "bid" and r["gold"] != "bid" for r in ok)
    fn = sum(r["pred"] != "bid" and r["gold"] == "bid" for r in ok)
    tn = sum(r["pred"] != "bid" and r["gold"] != "bid" for r in ok)
    scam = [r for r in ok if r["gold_scam"]]
    legit = [r for r in ok if not r["gold_scam"]]
    priced = [r for r in ok if r.get("price") is not None]
    claims_b = sum(r.get("claims", 0) for r in ok)
    uns_b = sum(r.get("unsupported_before", 0) for r in ok)
    uns_a = sum(r.get("unsupported_after", 0) for r in ok)
    claims_a = claims_b - (uns_b - uns_a)
    drafts = [r for r in ok if r.get("drafted")]
    return {
        "n": len(rows), "errors": len(rows) - len(ok),
        "bid_f1": round(f1(tp, fp, fn), 4), "accuracy": round((tp + tn) / len(ok), 4) if ok else None,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "scam_recall": round(sum(r["pred"] == "skip" and r["scam_score"] >= 0.5 for r in scam) / len(scam), 4) if scam else None,
        "scam_skip_rate": round(sum(r["pred"] == "skip" for r in scam) / len(scam), 4) if scam else None,
        "false_scam_rate": round(sum(r["scam_score"] >= 0.5 for r in legit) / len(legit), 4) if legit else None,
        "price_in_band": round(sum(r["in_band"] for r in priced) / len(priced), 4) if priced else None,
        "proposals_drafted": len(drafts),
        "unsupported_claim_rate_before": round(uns_b / claims_b, 4) if claims_b else None,
        "unsupported_claim_rate_after": round(uns_a / claims_a, 4) if claims_a else None,
        "claims_checked": claims_b,
        "p50_latency_s": round(pct([r["latency_s"] for r in ok], 50), 2), "p95_latency_s": round(pct([r["latency_s"] for r in ok], 95), 2),
        "p95_latency_s_proposal": round(pct([r["latency_s"] for r in drafts], 95), 2) if drafts else None,
        "mean_cost_usd_job": round(mean([r["cost_usd"] for r in ok]), 6), "mean_cost_usd_proposal": round(mean([r["cost_usd"] for r in drafts]), 6) if drafts else None,
        "mean_tokens_job": round(mean([r["tokens"] for r in ok]), 1),
        "marketplace_would_accept": sum(r.get("would_be_accepted") is True for r in rows),
        "marketplace_would_reject": sum(r.get("would_be_accepted") is False for r in rows),
        "dead_letter": sum(r.get("status") == "dead_letter" for r in rows), "needs_attention": sum(r.get("status") == "needs_attention" for r in rows),
    }


async def run_one(job: dict, user: dict, defences: dict | None) -> dict:
    from agent.runner import run_bid
    lab = job["labels"]
    t0 = time.perf_counter()
    row = {"job_id": job["job_id"], "persona": job["persona"], "gold": lab["gold_decision"], "gold_scam": lab["scam"],
           "injection": lab.get("injection"), "fit_level": lab["fit_level"], "band": lab["fair_price_band"]}
    try:
        out = await run_bid(user, {"job_id": job["job_id"]}, defences=defences)
    except Exception as e:  # noqa: BLE001
        row.update(error=f"{type(e).__name__}: {str(e)[:300]}", latency_s=time.perf_counter() - t0, pred="skip", scam_score=0, cost_usd=0, tokens=0, in_band=False)
        return row
    dec = (out.get("decision") or {}).get("action") or ("skip" if out["status"] in ("skipped", "dead_letter") else "watch")
    price = (out.get("price") or {}).get("amount")
    draft = out.get("draft") or {}
    ver = draft.get("verification") or {}
    row.update(status=out["status"], pred="bid" if dec == "bid" else "skip", raw_decision=dec, fit=(out.get("fit") or {}).get("fit_score"),
               scam_score=(out.get("risk") or {}).get("scam_score", 0), risk=(out.get("risk") or {}).get("risk_score"),
               price=price, in_band=bool(price is not None and lab["fair_price_band"][0] <= price <= lab["fair_price_band"][1]),
               drafted=bool(draft.get("cover_letter")), claims=(ver.get("before") or {}).get("claims", 0),
               unsupported_before=draft.get("unsupported_before", 0), unsupported_after=draft.get("unsupported_after", 0),
               latency_s=out["latency_s"], tokens=out["tokens"], cost_usd=out["cost_usd"], steps=out["steps"],
               cover_letter=draft.get("cover_letter"), compliance=(out.get("compliance") or {}).get("violations"),
               by_node={t["node"]: {"ms": t["ms"], "tokens": t["tokens"], "cost": t["cost_usd"]} for t in out.get("trace", [])},
               trace_id=out["trace_id"], errors=out.get("errors"),
               platform_violations=(out.get("preview") or {}).get("platform_violations"),
               would_be_accepted=(out.get("preview") or {}).get("would_be_accepted"))
    return row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20, help="jobs per persona")
    ap.add_argument("--persona", default=None)
    ap.add_argument("--out", default="decision_eval.json")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--no-stack", action="store_true", help="assume GigSim + MCP servers already running")
    ap.add_argument("--concurrency", type=int, default=int(os.environ.get("EVAL_CONCURRENCY", "3")))
    ap.add_argument("--jobs-file", default=None, help="alternative labelled jobs file (e.g. hidden test)")
    a = ap.parse_args()
    sys.path.insert(0, "scripts")
    import run_stack
    ps = None if a.no_stack else run_stack.start({"GIGSIM_ERROR_RATE": os.environ.get("GIGSIM_ERROR_RATE", "0.02"),
                                                  "GIGSIM_DB": os.environ.get("GIGSIM_DB", "var/eval_gigsim.db")})
    try:
        if a.jobs_file:
            jobs = [json.loads(line) for line in open(a.jobs_file)]
        else:
            jobs = load_dev(a.persona, a.limit)
        sem = asyncio.Semaphore(a.concurrency)

        async def guarded(j):
            async with sem:
                user = {"user_id": f"eval-{j['persona']}", "persona": j["persona"], "gigsim_key": f"gs-key-{j['persona']}"}
                r = await run_one(j, user, None)
                print(f"{r['job_id']} gold={r['gold']} pred={r.get('raw_decision', r['pred'])} fit={r.get('fit')} scam={r.get('scam_score')} "
                      f"price={r.get('price')} band={r['band']} {r.get('latency_s', 0):.1f}s ${r.get('cost_usd', 0):.5f} {r.get('error', '')}", flush=True)
                return r

        async def all_():
            return await asyncio.gather(*[guarded(j) for j in jobs])
        rows = asyncio.run(all_())
    finally:
        if ps:
            run_stack.stop(ps)
    summ = score(rows)
    by_persona = {p: score([r for r in rows if r["persona"] == p]) for p in sorted({r["persona"] for r in rows})}
    from agent import settings
    payload = {"provenance": provenance({"profile": settings.get("profile"), "rag_variant": settings.get("rag.variant"),
                                         "models": {k: settings.model_for(k) for k in ("analyst", "writer", "critic")}}),
               "summary": summ, "by_persona": by_persona, "declared_budgets": settings.get("budgets.declared"), "rows": rows}
    write_result(a.out, payload)
    print(json.dumps(summ, indent=1))
    if a.gate:
        fails = []
        if summ["bid_f1"] < GATES["bid_f1_min"]:
            fails.append(f"bid F1 {summ['bid_f1']} < {GATES['bid_f1_min']}")
        if (summ["unsupported_claim_rate_after"] or 0) > GATES["unsupported_after_max"]:
            fails.append(f"unsupported claims after verification {summ['unsupported_claim_rate_after']} > {GATES['unsupported_after_max']}")
        if fails:
            print("EVAL GATE FAILED: " + "; ".join(fails))
            sys.exit(1)
        print("eval gate passed")


if __name__ == "__main__":
    main()
    RESULTS  # noqa: B018
