import asyncio, json, sys
sys.path.insert(0, "scripts")
import run_stack
from agent.runner import run_bid, resume_bid, approval_token_for
ps = run_stack.start()
try:
    jobs = [json.loads(l) for l in open("evals/datasets/dev_set.jsonl")]
    job = next(j for j in jobs if j["persona"] == "ai_ml_engineer" and j["labels"]["gold_decision"] == "bid" and j["budget_type"] == "fixed")
    from agent import settings; settings.cfg()["thresholds"]["fit_bid"] = 0.0; settings.cfg()["thresholds"]["fit_watch"] = 0.0
    user = {"user_id": "u-test", "persona": "ai_ml_engineer", "gigsim_key": "gs-key-ai_ml_engineer"}
    events = []
    out = asyncio.run(run_bid(user, {"job_id": job["job_id"]}, emit=lambda n, k, p: events.append((n, k))))
    print("STATUS", out["status"], out["status_reason"])
    print("decision", out["decision"])
    print("fit", out["fit"] and out["fit"]["fit_score"], "risk", out["risk"] and out["risk"].get("risk_score"))
    print("price", out["price"] and out["price"]["amount"], out["price"] and out["price"]["rationale"])
    print("errors", out["errors"])
    print("draft", (out["draft"] or {}).get("cover_letter", "")[:500])
    print("ver", (out["draft"] or {}).get("verification"))
    print("events", len(events), events[:12])
    if out["pending_approval"]:
        p = out["pending_approval"]
        tok = approval_token_for(user["user_id"], p)
        out2 = asyncio.run(resume_bid(user, out["thread_id"], {"action": "approve", "approval_token": tok}))
        print("AFTER APPROVE", out2["status"], out2["submission"])
        # replay the approve: must not double-submit
    import httpx
    A={"X-Admin-Key":"gigsim-admin"}; H={"X-GigSim-Key":"gs-key-ai_ml_engineer"}
    print(httpx.post("http://localhost:8100/v1/admin/flush", headers=A).json())
    th = httpx.get("http://localhost:8100/v1/threads", headers=H).json()["threads"]
    print("threads", [(t["thread_id"], t["state"]) for t in th])
    if th:
        from agent.runner import run_conversation, resume_conversation, message_token_for
        c = asyncio.run(run_conversation(user, th[0]["thread_id"], job=job, proposal=out2.get("submission")))
        print("CONV", c["status"], c["intent"] and c["intent"]["intent"], (c["reply"] or {}).get("text"), c["errors"])
        if c["pending_approval"]:
            p = c["pending_approval"]
            c2 = asyncio.run(resume_conversation(user, c["thread_id"], {"action":"approve","approval_token": message_token_for(user["user_id"], p)}))
            print("CONV SENT", c2["status"], c2.get("sent"))
finally:
    run_stack.stop(ps)
