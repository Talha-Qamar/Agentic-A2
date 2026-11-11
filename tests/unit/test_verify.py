from rag import verify as V
from rag.embed import OverlapReranker

EV = [{"evidence_id": "e1", "text": "At Ticketly the median first response dropped from 9.2 h to 47 min using a triage agent."}]


def test_split_claims_ignores_plans():
    text = "At Ticketly I cut first response from 9.2 h to 47 min. My plan: (1) kickoff call. I can start this week."
    claims = V.split_claims(text)
    assert len(claims) == 1 and "Ticketly" in claims[0]


def test_fabricated_number_not_supported():
    cc = V.check_claim("c1", "At Ticketly I cut first response time by 95% in 2 days.", EV, OverlapReranker().score)
    assert cc.verdict in ("partial", "unsupported") and cc.missing_numbers


def test_grounded_claim_supported_and_removal():
    score = lambda q, docs: [0.9 for _ in docs]
    good = V.check_claim("c1", "At Ticketly the median first response dropped from 9.2 h to 47 min.", EV, score)
    assert good.verdict == "supported"
    bad = V.ClaimCheck("c2", "I built a rocket for NASA.", verdict="unsupported")
    text, removed = V.remove_unsupported("Intro sentence here. I built a rocket for NASA. Plan follows.", [good, bad])
    assert "NASA" not in text and removed == ["I built a rocket for NASA."]
