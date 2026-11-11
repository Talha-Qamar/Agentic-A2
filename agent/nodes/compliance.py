"""Compliance Guard: policy-pack rules + live platform policy. Fixes `fix`-severity issues, blocks `block`-severity
ones with a stated reason. Also used on human-edited text and on client-message replies."""
from __future__ import annotations

import re

from langgraph.graph import END
from langgraph.types import Command
from pydantic import BaseModel

from agent import settings
from agent.guardrails import output_violations, strip_violations
from agent.handoffs import ComplianceVerdict, Violation
from agent.llm import complete_json, load_prompt
from agent.nodes.runtime import Deps, node


class _LLMViolations(BaseModel):
    violations: list[Violation] = []


def disclosure_line(policy: dict) -> str | None:
    pack = settings.policy_rules()
    if (policy.get("requirements") or {}).get("ai_disclosure") or pack.get("disclosure", {}).get("required"):
        return pack.get("disclosure", {}).get("line") or "Drafted with AI assistance and reviewed by me."
    return None


async def check(text: str, policy: dict, use_llm: bool = True) -> ComplianceVerdict:
    pack = settings.policy_rules()
    severity = {r["id"]: r["severity"] for r in pack["rules"]}
    viol = [Violation(**v) for v in output_violations(text, tuple(pack.get("allowed_link_domains") or ()))]
    for ph in settings.get("proposal.banned_phrases", []):
        m = re.search(re.escape(ph), text, re.I)
        if m:
            viol.append(Violation(rule="banned_phrases", evidence="generic phrase", span=m.group(0)))
    if use_llm:
        try:
            rules = "\n".join(f"- {r['id']}: {r['text']}" for r in pack["rules"])
            llm = await complete_json("compliance", load_prompt("compliance").format(rules=rules), text, _LLMViolations, max_tokens=500)
            known = {(v.rule, v.span) for v in viol}
            viol += [v for v in llm.violations if (v.rule, v.span) not in known and v.span and v.span in text
                     and v.rule in severity and v.rule != "no_fabrication"]
        except Exception:  # noqa: BLE001 - deterministic checks still apply
            pass
    fixes, final = [], text
    fixable = [v.model_dump() for v in viol if severity.get(v.rule, "fix") == "fix"]
    if fixable:
        final = strip_violations(final, [f for f in fixable if f["rule"] != "banned_phrases"])
        for f in fixable:
            if f["rule"] == "banned_phrases":
                final = re.sub(re.escape(f["span"]), "", final, flags=re.I)
        final = re.sub(r"[ \t]{2,}", " ", final).strip()
        fixes = [f"{f['rule']}: removed '{f['span'][:60]}'" for f in fixable]
    line = disclosure_line(policy)
    if line and line.lower() not in final.lower():
        final = final.rstrip() + "\n\n" + line
        fixes.append("ai_disclosure: added required disclosure line")
    blocking = [v for v in viol if severity.get(v.rule, "fix") == "block"]
    return ComplianceVerdict(allowed=not blocking, violations=viol, fixes_applied=fixes, final_text=final,
                             blocked_reason=("; ".join(f"{v.rule}: {v.evidence} ('{v.span[:40]}')" for v in blocking) or None))


@node("compliance", retries=1)
async def compliance(state: dict, deps: Deps):
    draft = state["drafts"][-1]
    policy = (state.get("settings") or {}).get("policy") or {}
    v = await check(draft["cover_letter"], policy)
    if not v.allowed:
        return Command(goto=END, update={"compliance": v.model_dump(), "status": "blocked", "status_reason": v.blocked_reason})
    return Command(goto="preview", update={"compliance": v.model_dump(), "status": "previewing"})
