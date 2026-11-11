"""Style memory: learn from the freelancer's edits to approved proposals."""
from __future__ import annotations

import difflib
import json
import re
import time

from agent import settings
from agent.memory.promotion_rules import style_promotable
from agent.memory.store import get_store, ns

FILLER = ["i hope you are well", "i hope this finds you well", "i am excited", "i'm excited", "i would love to", "i am confident",
          "i believe", "please feel free", "thank you for your time", "looking forward to hearing from you", "!", "kindly"]


def sentences(t: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", t) if s.strip()]


def extract_candidates(before: str, after: str) -> list[dict]:
    """Diff -> candidate style patterns: {key, rule}."""
    out: list[dict] = []
    b, a = sentences(before), sentences(after)
    if b and a and b[0] != a[0] and b[0] not in a:
        out.append({"key": "opening:direct", "rule": "Open with the client's problem or your most relevant result; drop the "
                    f"kind of opening the user deleted (e.g. \"{b[0][:60]}\")."})
    bl, al = before.lower(), after.lower()
    for f in FILLER:
        if bl.count(f) > al.count(f):
            out.append({"key": f"avoid:{f}", "rule": f"Avoid the phrase \"{f}\"." if f != "!" else "Avoid exclamation marks."})
    wb, wa = len(re.findall(r"\w+", before)), len(re.findall(r"\w+", after))
    if wb and wa < wb * 0.8:
        out.append({"key": "length:shorter", "rule": f"Keep proposals short: about {max(60, int(wa / 10) * 10)} words."})
    elif wb and wa > wb * 1.25:
        out.append({"key": "length:longer", "rule": f"Proposals can be longer and more detailed: about {int(wa / 10) * 10} words."})
    if b and a and b[-1] != a[-1] and len(a[-1]) < 80:
        norm = re.sub(r"\W+", " ", a[-1].lower()).strip()
        out.append({"key": f"signoff:{norm[:40]}", "rule": f"End with: \"{a[-1]}\""})
    if re.search(r"^\s*[-*•]\s", after, re.M) and not re.search(r"^\s*[-*•]\s", before, re.M):
        out.append({"key": "format:bullets", "rule": "Use a short bulleted list for the plan or deliverables."})
    if re.search(r"\$\s?\d", before) and not re.search(r"\$\s?\d", after):
        out.append({"key": "price:omit", "rule": "Do not mention the price in the cover letter; the bid field carries it."})
    added = [s for s in a if s not in b and difflib.get_close_matches(s, b, n=1, cutoff=0.6) == []]
    for s in added[:1]:
        if re.search(r"(?i)\b(call|loom|video|walkthrough|demo)\b", s):
            out.append({"key": "add:call_offer", "rule": "Offer a short call or Loom walkthrough near the end."})
    return out


def record_edit(user_id: str, thread_id: str, before: str, after: str) -> dict:
    """Store the edit, update candidates and promote those that satisfy the promotion rule."""
    from common import db
    cands = extract_candidates(before, after)
    row = db.one("INSERT INTO edits(user_id, thread_id, before_text, after_text, diff, candidates) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                 (user_id, thread_id, before, after, json.dumps({"words_before": len(before.split()), "words_after": len(after.split())}),
                  json.dumps(cands)))
    eid = row["id"]
    recent = [r["id"] for r in db.q("SELECT id FROM edits WHERE user_id=%s ORDER BY id DESC LIMIT %s",
                                    (user_id, settings.get("memory.style.window_edits", 10)))][::-1]
    promoted = []
    for c in cands:
        r = db.one("""INSERT INTO memory_candidates(user_id, kind, key, value, occurrences, edit_ids) VALUES (%s,'style',%s,%s,1,ARRAY[%s]::bigint[])
                      ON CONFLICT (user_id, kind, key) DO UPDATE SET occurrences = memory_candidates.occurrences + 1,
                      edit_ids = array_append(memory_candidates.edit_ids, %s), value = EXCLUDED.value, updated_at = now()
                      RETURNING occurrences, edit_ids, promoted""", (user_id, c["key"], json.dumps(c), eid, eid))
        if not r["promoted"] and style_promotable(r["occurrences"], list(r["edit_ids"]), recent):
            get_store().put(ns(user_id, "style"), c["key"], {"rule": c["rule"], "occurrences": r["occurrences"],
                                                             "evidence_edits": list(r["edit_ids"]), "promoted_at": time.time()})
            db.x("UPDATE memory_candidates SET promoted=true WHERE user_id=%s AND kind='style' AND key=%s", (user_id, c["key"]))
            promoted.append(c["key"])
    return {"edit_id": eid, "candidates": [c["key"] for c in cands], "promoted": promoted}


def load_style_rules(user_id: str) -> list[str]:
    items = get_store().search(ns(user_id, "style"), limit=50)
    items = sorted(items, key=lambda it: -it.value.get("occurrences", 0))[: settings.get("memory.style.max_rules", 12)]
    return [it.value["rule"] for it in items]
