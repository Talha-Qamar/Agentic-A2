"""Proposal Writer: evidence-cited cover letter + screening answers (strong model)."""
from __future__ import annotations

import re

from pydantic import BaseModel

from agent import settings
from agent.guardrails import wrap_untrusted
from agent.handoffs import Claim, ProposalDraft, ScreeningAnswer
from agent.llm import complete_json, load_prompt
from agent.nodes.runtime import Deps, node


class _WriterOut(BaseModel):
    cover_letter: str
    screening_answers: list[ScreeningAnswer] = []
    claims: list[Claim] = []


def evidence_block(evidence: list[dict], limit: int = 10) -> str:
    lines = []
    for e in evidence[:limit]:
        meta = ", ".join(x for x in [e.get("type"), e.get("date"), f"outcome={e['outcome']}" if e.get("outcome") else None] if x)
        lines.append(f"[{e['evidence_id']}] ({meta}) {e.get('title', '')}\n{e['text'][:700]}")
    return "\n\n".join(lines) if lines else "(no evidence found)"


def policy_requirements(state: dict) -> str:
    pol = (state.get("settings") or {}).get("policy") or {}
    pack = settings.policy_rules()
    out = []
    if (pol.get("requirements") or {}).get("ai_disclosure") or pack.get("disclosure", {}).get("required"):
        line = pack.get("disclosure", {}).get("line") or "Drafted with AI assistance and reviewed by me."
        out.append(f"8. End the cover letter with this exact disclosure line: \"{line}\"")
    return "\n".join(out)


@node("writer", retries=1)
async def writer(state: dict, deps: Deps) -> dict:
    job, spec, price = state["job"], state["job_spec"], state.get("price") or {}
    evidence = list(state.get("evidence") or [])
    # extra evidence for screening questions
    for q in (spec.get("screening_questions") or [])[:3]:
        try:
            res = await deps.call("writer", "search_evidence", {"requirement": q[:400], "k": 2})
            evidence += [e for e in res.get("items", []) if e["evidence_id"] not in {x["evidence_id"] for x in evidence}]
        except Exception:  # noqa: BLE001
            pass
    p = settings.get("proposal")
    sys = load_prompt("writer").format(max_words=p["max_words"], min_words=p["min_words"], policy_requirements=policy_requirements(state),
                                       style_rules="\n".join(f"- {r}" for r in deps.style_rules) or "- (none learned yet)",
                                       outcome_insights="\n".join(f"- {i if isinstance(i, str) else i.get('text', '')}" for i in deps.outcome_insights) or "- (no outcome data yet)")
    fit = state.get("fit") or {}
    req_lines = "\n".join(f"- {m['requirement']} -> support: {m['support']} (evidence: {', '.join(m['evidence_ids']) or 'none'})"
                          for m in fit.get("matches", []))
    critique = ""
    if state.get("critiques"):
        last = state["critiques"][-1]
        critique = f"\n\nREVISION {state.get('revision', 0)}: the critic did not approve the previous draft. Apply these instructions:\n{last.get('instructions')}\nPrevious draft:\n{state['drafts'][-1]['cover_letter']}"
    regen = state.get("regenerate_paragraph")
    if regen is not None and state.get("drafts"):
        paras = re.split(r"\n\s*\n", state["drafts"][-1]["cover_letter"])
        critique += (f"\n\nRewrite ONLY paragraph {regen + 1} of this draft (keep every other paragraph word for word):\n"
                     + "\n\n".join(f"[P{i + 1}] {t}" for i, t in enumerate(paras)))
    body = wrap_untrusted(state.get("job_clean_text") or job["description"]) if deps.defences.get("delimit", True) else job["description"]
    user = (f"JOB SPEC: {spec.get('summary')}\nDeliverables: {spec.get('deliverables')}\nRequirements and evidence support:\n{req_lines}\n"
            f"Screening questions: {spec.get('screening_questions')}\nQuoted price: {price.get('bid_type')} ${price.get('amount')}\n\n"
            f"EVIDENCE (the only facts you may claim):\n{evidence_block(evidence)}\n\nJob post:\n{body}{critique}")
    out = await complete_json("writer", sys, user, _WriterOut, max_tokens=1600)
    version = len(state.get("drafts") or []) + 1
    words = len(re.findall(r"\w+", out.cover_letter))
    draft = ProposalDraft(version=version, cover_letter=out.cover_letter.strip(), screening_answers=out.screening_answers,
                          claims=out.claims, evidence_ids=sorted({i for c in out.claims for i in c.evidence_ids}), word_count=words)
    return {"drafts": [draft.model_dump()], "evidence": evidence, "regenerate_paragraph": None, "status": "verifying"}
