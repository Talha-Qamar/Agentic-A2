"""Outcome memory: what wins/replies per job category, promoted only with enough resolved samples."""
from __future__ import annotations

import json
import time

from agent.memory.promotion_rules import outcome_promotable
from agent.memory.store import get_store, ns

RESOLVED = {"replied", "interview", "hired", "lost"}
POSITIVE = {"replied", "interview", "hired"}


def record_outcome(user_id: str, category: str | None, proposal_id: str, outcome: str, cited: list[str] | None = None) -> dict:
    from common import db
    category = category or "uncategorised"
    key = f"cat:{category}"
    r = db.one("SELECT value FROM memory_candidates WHERE user_id=%s AND kind='outcome' AND key=%s", (user_id, key))
    v = (r or {}).get("value") or {"category": category, "proposals": {}, "cited_positive": {}}
    prev = v["proposals"].get(proposal_id)
    v["proposals"][proposal_id] = outcome
    if outcome in POSITIVE and prev not in POSITIVE:
        for c in cited or []:
            v["cited_positive"][c] = v["cited_positive"].get(c, 0) + 1
    db.x("""INSERT INTO memory_candidates(user_id, kind, key, value, occurrences) VALUES (%s,'outcome',%s,%s,1)
            ON CONFLICT (user_id, kind, key) DO UPDATE SET value=EXCLUDED.value, occurrences=memory_candidates.occurrences+1, updated_at=now()""",
         (user_id, key, json.dumps(v)))
    outs = list(v["proposals"].values())
    resolved = [o for o in outs if o in RESOLVED]
    promoted = False
    if outcome_promotable(len(resolved)):
        reply = sum(o in POSITIVE for o in resolved) / len(resolved)
        won = sum(o == "hired" for o in resolved) / len(resolved)
        top = sorted(v["cited_positive"].items(), key=lambda x: -x[1])[:3]
        text = (f"In {category}: {sum(o in POSITIVE for o in resolved)}/{len(resolved)} resolved proposals got a reply "
                f"({reply:.0%}), {won:.0%} hired." + (f" Evidence cited in replied proposals: {', '.join(t for t, _ in top)}." if top else ""))
        get_store().put(ns(user_id, "outcomes"), key, {"category": category, "reply_rate": round(reply, 3), "win_rate": round(won, 3),
                                                        "n": len(resolved), "text": text, "promoted_at": time.time()})
        promoted = True
    return {"category": category, "resolved": len(resolved), "promoted": promoted}


def load_outcome_insights(user_id: str) -> list[dict]:
    return [it.value for it in get_store().search(ns(user_id, "outcomes"), limit=50)]
