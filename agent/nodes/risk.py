"""Risk Assessor: deterministic red-flag rules + client history + LLM judgement.

The final scam score is max(rules, LLM): a job post cannot talk the LLM into lowering a rule-detected risk.
"""
from __future__ import annotations

import re

from agent.guardrails import wrap_untrusted
from agent.handoffs import RiskFlag, RiskReport
from agent.llm import complete_json, load_prompt
from agent.nodes.runtime import Deps, node

RULES = [
    ("off_platform", r"(telegram|whats\s?app|skype|signal)\b|outside the platform|off[- ]platform", 0.6, "high"),
    ("payment_scam", r"\b(crypto|usdt|bitcoin|wire transfer|western union|bank wire)\b|keep the difference|receive a check", 0.7, "high"),
    ("free_work", r"unpaid (test|trial)|free (sample|test)|complete the full project as (an )?unpaid", 0.55, "high"),
    ("credentials", r"(send|share) (your|me your) (platform )?(username|login|password)|username and password", 0.8, "high"),
    ("too_good_to_be_true", r"\$\s?[3-9]\d\d\s?/\s?(hour|hr)|no experience needed.*(start immediately|easy)", 0.5, "medium"),
]


def rule_report(text: str, client: dict, injection: dict) -> tuple[float, float, float, list[RiskFlag]]:
    flags, scam = [], 0.0
    for ftype, pat, w, sev in RULES:
        m = re.search(pat, text, re.I)
        if m:
            flags.append(RiskFlag(type=ftype, evidence=m.group(0)[:80], severity=sev))
            scam = max(scam, w)
    q = 0.5
    if client:
        q = 0.15
        q += 0.25 if client.get("payment_verified") else 0
        q += min(0.25, (client.get("total_spent") or 0) / 20000)
        q += min(0.2, (client.get("hires") or 0) / 25)
        q += 0.15 if (client.get("avg_rating") or 0) >= 4.5 else 0
        q = min(1.0, q)
        if client.get("payment_verified") is False:
            flags.append(RiskFlag(type="unverified_payment", evidence="payment method not verified", severity="medium"))
        if (client.get("hires") or 0) == 0 and (client.get("total_spent") or 0) == 0 and (client.get("account_age_days") or 999) < 30:
            flags.append(RiskFlag(type="low_quality_client", evidence=f"new account ({client.get('account_age_days')} days), no hires", severity="medium"))
            scam = max(scam, 0.2)
    if injection.get("injection_detected"):
        flags.append(RiskFlag(type="injection", evidence=", ".join(injection.get("injection_hits", []))[:80] or "instructions aimed at AI tools",
                              severity="medium"))
    risk = min(1.0, 0.65 * scam + 0.35 * (1 - q) + (0.1 if injection.get("injection_detected") else 0))
    return scam, risk, q, flags


async def _client(state: dict, deps: Deps) -> dict:
    cid = state["job"].get("client_id")
    if not cid:
        return {}
    try:
        return await deps.call("risk", "get_client_history", {"client_id": cid})
    except Exception:  # noqa: BLE001 - missing history is itself a (weak) signal, not a failure
        return {}


async def _fallback(state: dict, deps: Deps, err: Exception) -> dict:
    client = await _client(state, deps)
    prior = state.get("risk") or {}
    scam, risk, q, flags = rule_report(state.get("job_clean_text", ""), client, prior)
    rep = RiskReport(client_quality=q, scam_score=scam, risk_score=risk, flags=flags,
                     injection_detected=prior.get("injection_detected", False), injection_hits=prior.get("injection_hits", []),
                     quarantined_spans=prior.get("quarantined_spans", []),
                     recommendation="avoid" if scam >= 0.5 else ("caution" if risk >= 0.4 else "ok"),
                     reasons=["rules only (LLM unavailable)"])
    return {"risk": rep.model_dump() | {"client": client}}


@node("risk", fallback=_fallback, retries=1)
async def risk(state: dict, deps: Deps) -> dict:
    job = state["job"]
    prior = state.get("risk") or {}
    raw_text = f"{job['title']}\n\n{job['description']}"   # rules see the raw text, including quarantined spans
    client = await _client(state, deps)
    scam, rsk, q, flags = rule_report(raw_text, client, prior)
    body = wrap_untrusted(state.get("job_clean_text") or raw_text) if deps.defences.get("delimit", True) else raw_text
    user = (f"Client history: {client}\nBudget: {job.get('budget_type')} {job.get('budget_min')}-{job.get('budget_max')}\n"
            f"Rule-based flags already found: {[f.model_dump() for f in flags]}\nInjection detector: {prior.get('injection_hits')}\n\n"
            f"Job post:\n{body}")
    llm = await complete_json("risk", load_prompt("risk"), user, RiskReport)
    seen = {(f.type, f.evidence) for f in flags}
    merged_flags = flags + [f for f in llm.flags if (f.type, f.evidence) not in seen]
    rep = RiskReport(client_quality=round(min(q, llm.client_quality) if client else llm.client_quality, 3),
                     scam_score=round(max(scam, llm.scam_score), 3), risk_score=round(max(rsk, llm.risk_score), 3),
                     flags=merged_flags[:10], injection_detected=prior.get("injection_detected", False) or llm.injection_detected,
                     injection_hits=prior.get("injection_hits", []), quarantined_spans=prior.get("quarantined_spans", []),
                     recommendation=llm.recommendation if max(scam, llm.scam_score) < 0.5 else "avoid", reasons=llm.reasons[:5])
    return {"risk": rep.model_dump() | {"client": client}}
