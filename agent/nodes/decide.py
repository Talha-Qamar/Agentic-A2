"""Bid decision: a deterministic, explainable rule over evidence-based scores (thresholds in config).

An LLM never decides bid/skip directly, so text in a job post cannot argue its way to "BID" (injection defence 4).
"""
from __future__ import annotations

from langgraph.graph import END
from langgraph.types import Command

from agent import settings
from agent.handoffs import BidDecision
from agent.nodes.runtime import Deps, node


def decide_rule(fit: dict, risk: dict, job: dict, profile: dict, autonomy: str = "suggest") -> BidDecision:
    t = settings.get("thresholds")
    trace, reasons = [], []
    fs, scam, rsk = fit.get("fit_score", 0), risk.get("scam_score", 0), risk.get("risk_score", 0)
    floor = profile.get("hourly_floor", 20)
    bmax = job.get("budget_max") or 0
    if scam >= t["scam_skip"]:
        trace.append(f"scam_score {scam:.2f} >= {t['scam_skip']}")
        reasons.append("Likely scam: " + "; ".join(f["evidence"] for f in risk.get("flags", [])[:2] if f.get("severity") == "high"))
        return BidDecision(action="skip", confidence=round(scam, 2), reasons=reasons, rule_trace=trace)
    if rsk >= t["risk_skip"]:
        trace.append(f"risk_score {rsk:.2f} >= {t['risk_skip']}")
        return BidDecision(action="skip", confidence=round(rsk, 2), reasons=["Client/job risk too high"], rule_trace=trace)
    if job.get("budget_type") == "hourly" and bmax and bmax < floor * 0.8:
        trace.append(f"hourly budget max {bmax} < 0.8 x floor {floor}")
        return BidDecision(action="skip", confidence=0.8, reasons=[f"Budget (${bmax}/h) is below your floor (${floor}/h)"], rule_trace=trace)
    if job.get("budget_type") == "fixed" and bmax and bmax < floor * 4:
        trace.append(f"fixed budget {bmax} < 4h x floor {floor}")
        return BidDecision(action="skip", confidence=0.7, reasons=[f"Fixed budget ${bmax} is below 4 hours at your floor"], rule_trace=trace)
    if fs < t["fit_watch"]:
        trace.append(f"fit {fs:.2f} < watch threshold {t['fit_watch']}")
        auto = autonomy == "auto_skip" and fs < settings.get("autonomy.auto_skip_max_fit", 0.25)
        return BidDecision(action="skip", confidence=round(1 - fs, 2), auto_skipped=auto, rule_trace=trace,
                           reasons=["Weak portfolio fit: missing " + ", ".join(fit.get("gaps", [])[:3])])
    if fs < t["fit_bid"]:
        trace.append(f"{t['fit_watch']} <= fit {fs:.2f} < bid threshold {t['fit_bid']}")
        return BidDecision(action="watch", confidence=0.5, rule_trace=trace,
                           reasons=["Partial fit - worth watching", *fit.get("reasons", [])[:1]])
    trace.append(f"fit {fs:.2f} >= {t['fit_bid']}, risk {rsk:.2f} < {t['risk_skip']}, scam {scam:.2f} < {t['scam_skip']}")
    return BidDecision(action="bid", confidence=round(fs, 2), rule_trace=trace,
                       reasons=[*fit.get("reasons", [])[:1], "Strengths: " + "; ".join(fit.get("strengths", [])[:2])])


@node("decide", retries=0)
async def decide(state: dict, deps: Deps):
    if state.get("status") in ("dead_letter", "needs_attention"):
        return Command(goto=END, update={})
    if not state.get("fit") or not state.get("job_spec"):
        return Command(goto="dead_letter", update={"status": "dead_letter", "status_reason": "analysis incomplete"})
    autonomy = (deps.profile.get("settings") or {}).get("autonomy", settings.get("autonomy.default_level"))
    d = decide_rule(state["fit"], state.get("risk") or {}, state["job"], deps.profile, autonomy)
    status = {"bid": "pricing", "watch": "watching", "skip": "skipped"}[d.action]
    upd = {"decision": d.model_dump(), "status": status, "status_reason": d.reasons[0] if d.reasons else d.action}
    return Command(goto="pricing" if d.action == "bid" else END, update=upd)
