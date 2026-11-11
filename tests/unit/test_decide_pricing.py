from agent.nodes.decide import decide_rule
from agent.nodes.pricing import quote

PROFILE = {"hourly_floor": 35, "target_rate": 55}


def test_scam_skipped_even_with_high_fit():
    d = decide_rule({"fit_score": 0.95}, {"scam_score": 0.8, "risk_score": 0.5, "flags": [{"severity": "high", "evidence": "telegram"}]},
                    {"budget_type": "fixed", "budget_max": 2000}, PROFILE)
    assert d.action == "skip" and "scam" in d.rule_trace[0]


def test_bid_watch_skip_thresholds():
    job = {"budget_type": "fixed", "budget_max": 2000}
    risk = {"scam_score": 0.0, "risk_score": 0.2}
    from agent import settings
    t = settings.get("thresholds")
    assert decide_rule({"fit_score": t["fit_bid"] + 0.01}, risk, job, PROFILE).action == "bid"
    assert decide_rule({"fit_score": (t["fit_bid"] + t["fit_watch"]) / 2}, risk, job, PROFILE).action == "watch"
    assert decide_rule({"fit_score": t["fit_watch"] / 2, "gaps": ["x"]}, risk, job, PROFILE).action == "skip"


def test_low_hourly_budget_skipped():
    d = decide_rule({"fit_score": 0.9}, {"scam_score": 0, "risk_score": 0.1}, {"budget_type": "hourly", "budget_max": 10}, PROFILE)
    assert d.action == "skip"


def test_price_never_below_floor_and_within_budget():
    q = quote({"budget_type": "hourly", "budget_max": 60}, {"requirements": [1, 2]}, 0.8, {"hourly": {"p25": 15, "p50": 25, "p75": 40}}, PROFILE, 8, None)
    assert 35 <= q.amount <= 60
    f = quote({"budget_type": "fixed", "budget_max": 1000}, {"requirements": [1, 2, 3]}, 0.9, {}, PROFILE, 8, None)
    assert f.amount <= 1000 and f.connects_cost == 8 and f.rationale
