"""Critic: grades the verified draft; sends it back to the Writer at most `max_critic_revisions` times."""
from __future__ import annotations

import re

from langgraph.types import Command

from agent import settings
from agent.handoffs import Critique, CritiqueIssue
from agent.llm import complete_json, load_prompt
from agent.nodes.runtime import Deps, node
from agent.nodes.writer import evidence_block


def static_issues(draft: dict, spec: dict) -> list[CritiqueIssue]:
    p = settings.get("proposal")
    text = draft["cover_letter"]
    issues = []
    first = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0].lower()
    for ph in p["banned_phrases"]:
        if ph in text.lower():
            issues.append(CritiqueIssue(type="generic_opening" if ph in first else "tone", detail=f"remove the phrase '{ph}'"))
    w = len(re.findall(r"\w+", text))
    if w > p["max_words"] * 1.1:
        issues.append(CritiqueIssue(type="length", detail=f"{w} words; cut to under {p['max_words']}"))
    if w < p["min_words"] * 0.8:
        issues.append(CritiqueIssue(type="length", detail=f"only {w} words; add the plan and evidence"))
    if len(draft.get("screening_answers", [])) < len(spec.get("screening_questions", [])):
        issues.append(CritiqueIssue(type="screening", detail="answer every screening question"))
    return issues


@node("critic", retries=1)
async def critic(state: dict, deps: Deps):
    draft, spec = state["drafts"][-1], state["job_spec"]
    ver = draft.get("verification", {})
    user = (f"JOB SPEC: {spec.get('summary')}\nRequirements: {[r['text'] for r in spec.get('requirements', [])]}\n"
            f"Screening questions: {spec.get('screening_questions')}\n\nEVIDENCE available:\n{evidence_block(state.get('evidence') or [], 8)}\n\n"
            f"VERIFICATION: {ver.get('before')} -> removed {len(draft.get('removed_claims', []))} unsupported claims\n\n"
            f"DRAFT v{draft['version']}:\n{draft['cover_letter']}\n\nSCREENING ANSWERS: {draft.get('screening_answers')}")
    c = await complete_json("critic", load_prompt("critic"), user, Critique, max_tokens=700)
    extra = static_issues(draft, spec)
    c.issues += extra
    if extra and c.approved and any(i.type in ("generic_opening", "length") for i in extra):
        c.approved = False
        c.instructions = (c.instructions + " " + " ".join(i.detail for i in extra)).strip()
    rev = state.get("revision", 0)
    c.revision = rev
    if not c.approved and rev < settings.get("budgets.max_critic_revisions", 2):
        return Command(goto="writer", update={"critiques": [c.model_dump()], "revision": rev + 1, "status": "revising"})
    return Command(goto="compliance", update={"critiques": [c.model_dump()], "status": "compliance"})
