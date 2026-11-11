"""Pricing Strategist: market percentiles (real Upwork data via the marketplace port), the freelancer's floor,
the client's budget and the Connects cost -> a price with a rationale and an expected-value check."""
from __future__ import annotations

from langgraph.graph import END
from langgraph.types import Command

from agent import settings
from agent.handoffs import PriceQuote
from agent.nodes.runtime import Deps, node


def quote(job: dict, spec: dict, fit: float, market: dict, profile: dict, connects_cost: int, reply_prior: float | None) -> PriceQuote:
    p = settings.get("pricing")
    floor = float(profile.get("hourly_floor", 25))
    target = float(profile.get("target_rate", floor * 1.5))
    bmax = job.get("budget_max")
    if job.get("budget_type") == "hourly":
        h = market.get("hourly") or {}
        base = max(floor * (1 + p["hourly_markup_over_floor"]), min(target, h.get("p75", target)))
        amount = base * (0.9 + 0.2 * fit)
        if bmax and bmax >= floor:
            amount = min(amount, bmax)
        amount = round(max(amount, floor), 0)
        rationale = (f"Hourly: market p25/p50/p75 = ${h.get('p25', 0):.0f}/${h.get('p50', 0):.0f}/${h.get('p75', 0):.0f}; "
                     f"your floor ${floor:.0f}, target ${target:.0f}; client max ${bmax}. Fit {fit:.2f} -> ${amount:.0f}/h.")
        value = amount * 20  # value of a typical short hourly engagement (20 h) for the EV check
        bid_type = "hourly"
    else:
        n = max(1, len(spec.get("requirements", [])))
        hours = n * p["fixed_hours_per_requirement"]
        cost_based = hours * target
        if bmax:
            amount = min(bmax, max(bmax * (0.85 + 0.15 * fit), min(cost_based, bmax)))
            amount = max(amount, min(bmax, floor * hours * 0.5))
        else:
            f = market.get("fixed") or {}
            amount = max(cost_based, f.get("p50", cost_based))
        amount = round(amount / 5) * 5
        rationale = (f"Fixed: ~{hours} h of work ({n} requirements x {p['fixed_hours_per_requirement']} h) at target ${target:.0f}/h "
                     f"= ${cost_based:.0f}; client budget ${bmax}; fit {fit:.2f} -> ${amount:.0f}.")
        if bmax and cost_based > bmax * 1.3:
            rationale += f" Note: the work is worth about ${cost_based:.0f}; the client's budget is low - consider scoping down or skipping."
        value = amount
        bid_type = "fixed"
    p_reply = reply_prior if reply_prior is not None else 0.08 + 0.35 * fit
    ev = p_reply * 0.35 * value * 0.1          # P(reply) x P(hire|reply) x value x margin share attributable to this bid
    cusd = connects_cost * p["connect_usd"]
    worth = ev >= cusd * settings.get("thresholds.connects_ev_min_ratio", 1.0)
    return PriceQuote(bid_type=bid_type, amount=float(amount), floor=floor, market=market, client_budget_max=bmax,
                      connects_cost=connects_cost, connects_usd=round(cusd, 2), p_reply_estimate=round(p_reply, 3),
                      expected_value_usd=round(ev, 2), worth_connects=worth, rationale=rationale)


@node("pricing", retries=1)
async def pricing(state: dict, deps: Deps):
    job, spec = state["job"], state["job_spec"]
    market = await deps.call("pricing", "get_market_stats", {"category": job.get("category")})
    cost = job.get("connects_cost")
    if cost is None:
        cost = (await deps.call("scout", "get_job", {"job_id": job["job_id"]})).get("connects_cost") or 0
    prior = None
    for ins in deps.outcome_insights:
        if isinstance(ins, dict) and ins.get("category") == job.get("category"):
            prior = ins.get("reply_rate")
    q = quote(job, spec, state["fit"]["fit_score"], market, deps.profile, int(cost), prior)
    try:
        policy = await deps.call("pricing", "get_policy", {})
    except Exception:  # noqa: BLE001
        policy = {}
    settings_upd = dict(state.get("settings") or {}, policy=policy)
    if not q.worth_connects:
        return Command(goto=END, update={"price": q.model_dump(), "status": "watching",
                                         "status_reason": f"Expected value ${q.expected_value_usd} < Connects cost ${q.connects_usd}",
                                         "settings": settings_upd})
    return Command(goto="writer", update={"price": q.model_dump(), "status": "drafting", "revision": 0, "settings": settings_upd})
