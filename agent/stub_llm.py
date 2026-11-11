"""Deterministic offline stand-in for an LLM. TESTS AND CI ONLY (profile `stub`).

It lets unit/integration/Playwright tests exercise the full graph without network or secrets. It is never used for
any number reported in evals/results or the report (provenance records the profile of every result file).
"""
from __future__ import annotations

import json
import re


def _untrusted(text: str) -> str:
    m = re.search(r"<untrusted_[a-z_]+_[0-9a-f]+>\n(.*?)\n</untrusted", text, re.S)
    return m.group(1) if m else text


def _evidence(text: str) -> list[tuple[str, str]]:
    return re.findall(r"\[([^\]\s]+:\d+)\] \([^)]*\) [^\n]*\n([^\n]+)", text)


def stub_complete(node: str, messages: list[dict]) -> str:
    user = messages[-1]["content"]
    if node == "analyst":
        body = _untrusted(user)
        reqs = [ln.strip("- ").strip() for ln in body.splitlines() if ln.strip().startswith("- ")][:6] or [body.splitlines()[0][:120]]
        q = re.findall(r"^\d+\. (.+)$", body, re.M)
        return json.dumps({"summary": body.splitlines()[0][:120], "deliverables": reqs[:2],
                           "requirements": [{"id": f"r{i + 1}", "text": r, "skills": [], "must_have": True} for i, r in enumerate(reqs)],
                           "skills": [], "screening_questions": q, "hidden_needs": []})
    if node == "risk":
        scam = 0.7 if re.search(r"(?i)telegram|whatsapp|crypto|unpaid|password", user) else 0.05
        return json.dumps({"client_quality": 0.6, "scam_score": scam, "risk_score": 0.2 + scam / 2, "flags": [],
                           "recommendation": "avoid" if scam > 0.5 else "ok", "reasons": ["stub assessment"]})
    if node == "writer":
        ev = _evidence(user)
        reqs = re.findall(r"^- (.+?) -> support", user, re.M)
        need = reqs[0] if reqs else "this project"
        claims, paras = [], [f"You need {need[:100].rstrip('.')}, and I have shipped similar work."]
        for eid, line in ev[:2]:
            sent = re.split(r"(?<=[.!?])\s", line.strip())[0][:220]
            if len(sent) > 30:
                claim = f"Previously: {sent.rstrip('.')}."
                paras.append(claim)
                claims.append({"text": claim, "evidence_ids": [eid]})
        paras.append("My plan: (1) confirm scope and success metrics in a kickoff call; (2) ship a working first version in week one; "
                     "(3) add tests and documentation before handover so your team can own it.")
        paras.append("I can start this week and keep you updated twice a week.")
        qs = re.findall(r"Screening questions: \[(.*?)\]", user)
        qlist = re.findall(r"'([^']+)'", qs[0]) if qs else []
        return json.dumps({"cover_letter": "\n\n".join(paras), "claims": claims,
                           "screening_answers": [{"question": q, "answer": "Yes - see the project described above; happy to share details.",
                                                  "evidence_ids": [ev[0][0]] if ev else []} for q in qlist]})
    if node == "critic":
        return json.dumps({"approved": True, "score": 8, "issues": [], "instructions": ""})
    if node == "compliance":
        return json.dumps({"violations": []})
    if node == "verifier":
        return json.dumps({"verdict": "partial", "reason": "stub judge"})
    if node == "intent":
        t = _untrusted(user).lower()
        intent = ("scam_signal" if re.search(r"whatsapp|crypto|free sample|your email", t) else "interview_request" if re.search(r"call|interview|schedule", t)
                  else "negotiation" if re.search(r"\$|budget|rate", t) else "question")
        return json.dumps({"intent": intent, "confidence": 0.7, "summary": t[:80], "injection_detected": "ignore previous" in t})
    if node == "liaison":
        slots = re.findall(r"label: (.+)", user)[:2]
        txt = "Thanks for your message. " + (f"I am free {slots[0]} or {slots[1]} - which works for you?" if len(slots) == 2 else
                                             "Happy to keep everything on the platform and answer any questions here.")
        return json.dumps({"text": txt, "proposed_slots": [{"start": "", "label": s} for s in slots], "evidence_ids": [], "counter_offer": None, "notes": []})
    if node == "judge":
        return json.dumps({"score": 6, "reason": "stub"})
    if node == "hyde":
        return "I built a production system with the requested tools and measured results."
    return json.dumps({"text": "stub"})
