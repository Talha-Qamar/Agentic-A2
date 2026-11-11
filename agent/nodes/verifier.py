"""Claim verification node (B3): every claim in the draft is checked against portfolio evidence retrieved through
the Portfolio MCP server; unsupported claims are removed BEFORE the critic sees the draft."""
from __future__ import annotations

from pydantic import BaseModel

from agent import settings
from agent.llm import complete_json, load_prompt
from agent.nodes.runtime import Deps, node
from rag import verify as V


class _Judge(BaseModel):
    verdict: str
    reason: str = ""


def _score_fn():
    try:
        from rag.embed import get_reranker
        rr = get_reranker()
        return rr.score
    except Exception:  # noqa: BLE001
        from rag.embed import OverlapReranker
        return OverlapReranker().score


async def check_text(text: str, deps: Deps, cited: list[dict], agent: str = "critic") -> list[V.ClaimCheck]:
    score = _score_fn()
    checks = []
    for i, claim in enumerate(V.split_claims(text)):
        cands = {e["evidence_id"]: e for e in cited}
        try:
            res = await deps.call(agent, "search_evidence", {"requirement": claim[:480], "k": 5})
            for e in res.get("items", []):
                cands.setdefault(e["evidence_id"], e)
        except Exception:  # noqa: BLE001
            pass
        cc = V.check_claim(f"c{i + 1}", claim, list(cands.values()), score)
        if cc.verdict == "partial" and settings.get("verification.use_llm_judge", True):
            ev = "\n\n".join(cands[e]["text"][:800] for e in cc.evidence_ids if e in cands)
            try:
                j = await complete_json("verifier", load_prompt("verifier_judge"), f"CLAIM: {claim}\n\nEVIDENCE:\n{ev}", _Judge, max_tokens=200)
                if j.verdict in ("supported", "partial", "unsupported"):
                    cc.note = (cc.note + f" | judge: {j.verdict} ({j.reason[:80]})").strip(" |")
                    cc.verdict = j.verdict if not (cc.missing_numbers and j.verdict == "supported") else "partial"
            except Exception:  # noqa: BLE001
                pass
        checks.append(cc)
    return checks


@node("verifier", retries=1)
async def verifier(state: dict, deps: Deps) -> dict:
    draft = dict(state["drafts"][-1])
    ev_by_id = {e["evidence_id"]: e for e in state.get("evidence") or []}
    cited = [ev_by_id[i] for i in draft.get("evidence_ids", []) if i in ev_by_id]
    checks = await check_text(draft["cover_letter"], deps, cited)
    before = V.summary(checks)
    if deps.defences.get("verify", True):
        clean, removed = V.remove_unsupported(draft["cover_letter"], checks)
    else:
        clean, removed = draft["cover_letter"], []
    after_checks = [c for c in checks if c.text not in removed]
    after = V.summary(after_checks)
    draft.update(cover_letter=clean, claims=[{"id": c.id, "text": c.text, "evidence_ids": c.evidence_ids, "verdict": c.verdict,
                                              "score": c.score, "note": c.note} for c in checks],
                 unsupported_before=before["unsupported"], unsupported_after=after["unsupported"], removed_claims=removed,
                 verification={"before": before, "after": after})
    return {"drafts": [draft], "status": "critiquing"}
