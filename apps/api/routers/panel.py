"""Human evaluation: blind pairwise panel (/panel) and judge-calibration labelling (/label). Public pages, no login;
items come from evals/results (panel_pairs.json, judge_items.json) and votes are stored in Postgres."""
from __future__ import annotations

import json
import random

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agent import settings
from common import db

router = APIRouter(prefix="/api/panel", tags=["human-eval"])
RES = settings.ROOT / "evals" / "results"


def _load(name: str) -> list[dict]:
    p = RES / name
    return json.loads(p.read_text()).get("items", []) if p.exists() else []


@router.get("/pair")
def next_pair(rater: str):
    pairs = _load("panel_pairs.json")
    done = {r["pair_id"] for r in db.q("SELECT pair_id FROM panel_votes WHERE rater=%s", (rater[:60],))}
    todo = [p for p in pairs if p["pair_id"] not in done]
    if not todo:
        return {"done": True, "total": len(pairs)}
    p = random.Random(rater).choice(todo)
    flip = random.Random(rater + p["pair_id"]).random() < 0.5   # blind + randomised sides
    a, b = (p["b"], p["a"]) if flip else (p["a"], p["b"])
    return {"pair_id": p["pair_id"], "job": p["job"], "A": a["text"], "B": b["text"], "flip": flip, "remaining": len(todo), "total": len(pairs)}


class VoteIn(BaseModel):
    pair_id: str
    rater: str = Field(min_length=2, max_length=60)
    choice: str = Field(pattern="^(A|B|tie)$")
    flip: bool


@router.post("/vote")
def vote(v: VoteIn):
    real = v.choice if v.choice == "tie" else ({"A": "b", "B": "a"}[v.choice] if v.flip else {"A": "a", "B": "b"}[v.choice])
    db.x("INSERT INTO panel_votes(pair_id, rater, choice) VALUES (%s,%s,%s) ON CONFLICT (pair_id, rater) DO UPDATE SET choice=EXCLUDED.choice",
         (v.pair_id, v.rater, real))
    return {"ok": True}


@router.get("/label")
def next_label(labeller: str):
    items = _load("judge_items.json")
    done = {r["item_id"] for r in db.q("SELECT item_id FROM judge_labels")}
    todo = [i for i in items if i["item_id"] not in done]
    if not todo:
        return {"done": True, "total": len(items)}
    i = todo[0]
    return {"item_id": i["item_id"], "job": i["job"], "proposal": i["proposal"], "remaining": len(todo), "total": len(items)}


class LabelIn(BaseModel):
    item_id: str
    labeller: str = Field(min_length=2, max_length=60)
    score: float = Field(ge=1, le=10)


@router.post("/label")
def label(v: LabelIn):
    db.x("INSERT INTO judge_labels(item_id, label, labeller) VALUES (%s,%s,%s) ON CONFLICT (item_id) DO UPDATE SET label=EXCLUDED.label",
         (v.item_id, v.score, v.labeller))
    return {"ok": True}


@router.get("/export")
def export():
    """Anonymised export for evals/runners/human_eval.py (votes and labels, no rater names)."""
    votes = db.q("SELECT pair_id, md5(rater) rater, choice FROM panel_votes")
    labels = db.q("SELECT item_id, label FROM judge_labels")
    if not votes and not labels:
        raise HTTPException(404, "no human data yet")
    return {"votes": votes, "labels": labels}
