import os
import tempfile

from fastapi.testclient import TestClient

os.environ["GIGSIM_DB"] = tempfile.mktemp(suffix=".db")
from gigsim.app import app  # noqa: E402
from gigsim.policy import connects_cost, load_policy  # noqa: E402

H = {"X-GigSim-Key": "gs-key-ai_ml_engineer"}
A = {"X-Admin-Key": "gigsim-admin"}
LETTER = "At PeopleFirst I built a Teams bot over HR policies that cut ticket volume 41% in three months. " * 3


def test_policy_versions_cost():
    job = {"budget_type": "fixed", "budget_max": 1800}
    assert connects_cost(load_policy("2026-10-27"), job) == 8
    assert connects_cost(load_policy("2026-11-02"), job) == 10


def test_submit_is_exactly_once_and_spends_connects():
    with TestClient(app) as c:
        c.post("/v1/admin/seed", headers=A)
        jid = c.get("/v1/jobs", params={"pool": "dev", "persona": "ai_ml_engineer"}, headers=H).json()["jobs"][0]["job_id"]
        bal0 = c.get("/v1/account", headers=H).json()["connects_balance"]
        d = c.post("/v1/proposals/drafts", json={"job_id": jid, "cover_letter": LETTER, "bid_amount": 500, "idempotency_key": "kkkkkkkk-1"}, headers=H).json()
        dry = c.post(f"/v1/proposals/{d['proposal_id']}/submit", json={"idempotency_key": "ssssssss-1", "dry_run": True}, headers=H).json()
        assert dry["dry_run"] and dry["would_send"]["cover_letter"] == LETTER
        s1 = c.post(f"/v1/proposals/{d['proposal_id']}/submit", json={"idempotency_key": "ssssssss-1"}, headers=H).json()
        s2 = c.post(f"/v1/proposals/{d['proposal_id']}/submit", json={"idempotency_key": "ssssssss-1"}, headers=H).json()
        assert s1["status"] == "submitted" and s2.get("idempotent_replay")
        assert c.get("/v1/account", headers=H).json()["connects_balance"] == bal0 - dry["connects_cost"]


def test_policy_update_requires_disclosure():
    with TestClient(app) as c:
        c.post("/v1/admin/seed", headers=A)
        c.post("/v1/admin/policy", json={"version": "2026-11-02"}, headers=A)
        jid = c.get("/v1/jobs", params={"pool": "dev", "persona": "ai_ml_engineer"}, headers=H).json()["jobs"][1]["job_id"]
        d = c.post("/v1/proposals/drafts", json={"job_id": jid, "cover_letter": LETTER, "bid_amount": 500, "idempotency_key": "kkkkkkkk-2"}, headers=H).json()
        r = c.post(f"/v1/proposals/{d['proposal_id']}/submit", json={"idempotency_key": "ssssssss-2"}, headers=H)
        assert r.status_code == 422 and "ai_disclosure" in r.text
        c.post("/v1/admin/policy", json={"version": "2026-10-27"}, headers=A)


def test_rate_limit_and_auth():
    with TestClient(app) as c:
        assert c.get("/v1/account", headers={"X-GigSim-Key": "nope"}).status_code == 401
