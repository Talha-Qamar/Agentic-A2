"""analyse_job never re-runs a finished analysis (a re-run on the same thread would also eat its step budget)."""
import asyncio

import worker.tasks as T


def test_finished_job_is_not_reanalysed(monkeypatch):
    calls = []
    monkeypatch.setattr(T, "user_row", lambda uid: {"user_id": uid})
    monkeypatch.setattr(T.db, "one", lambda sql, args=None: {"job_id": "j1", "thread_id": "bid-x-j1-1", "status": "skipped"})
    monkeypatch.setattr(T.db, "x", lambda *a, **k: calls.append(a))
    out = asyncio.run(T.analyse_job(None, "user-1", "j1"))
    assert out == {"thread_id": "bid-x-j1-1", "status": "skipped", "already_analysed": True}
    assert calls == []   # nothing written, no run started


def test_dead_letter_retry_gets_a_fresh_thread(monkeypatch):
    import agent.runner
    seen = {}

    async def fake_run_bid(user, job, thread_id=None, emit=None):
        seen["thread_id"] = thread_id
        return {"status": "skipped"}
    monkeypatch.setattr(agent.runner, "run_bid", fake_run_bid)
    monkeypatch.setattr(T, "user_row", lambda uid: {"user_id": uid})
    monkeypatch.setattr(T.db, "one", lambda sql, args=None: {"job_id": "j1", "thread_id": "bid-x-j1-1", "status": "dead_letter"})
    monkeypatch.setattr(T.db, "x", lambda *a, **k: None)
    monkeypatch.setattr(T.db, "q", lambda *a, **k: [])
    monkeypatch.setattr(T, "save_state_snapshot", lambda *a: None)
    monkeypatch.setattr(T, "record_run", lambda *a, **k: None)
    asyncio.run(T.analyse_job(None, "user-1", "j1"))
    assert seen["thread_id"] != "bid-x-j1-1"
