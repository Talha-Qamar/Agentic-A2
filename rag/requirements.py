"""Deterministic requirement extraction from a job post (used by V1+ retrieval and by the Fit
Matcher, which runs in parallel with the LLM Job Analyst and so cannot wait for its JobSpec)."""
from __future__ import annotations

import re

from agent.guardrails import quarantine

SKIP = re.compile(r"(?i)^(hi|hello|about us|we are|we're|i run|looking for an experienced|timeline|expected duration|"
                  r"we'd like this done|budget|fixed budget|hourly rate|please answer|\d+\.|what we need|requirements|"
                  r"you will|scope|must haves|thanks|serious freelancers)")
NEED_HINT = re.compile(r"(?i)(experience|must|need|required|know|using|with|build|hands-on|comfortable|work|"
                       r"should|ability|familiar|skills?|for example|deliver)")


def extract_requirements(text: str, max_n: int = 8) -> list[dict]:
    clean, _ = quarantine(text or "")
    # ignore the screening-question block
    clean = re.split(r"(?im)^please answer:?$", clean)[0]
    cands: list[str] = []
    for line in clean.splitlines():
        line = line.strip(" -*\t")
        if not line or SKIP.search(line):
            continue
        for sent in re.split(r"(?<=[.!?])\s+", line):
            sent = sent.strip()
            if 8 <= len(sent) <= 220 and NEED_HINT.search(sent) and not SKIP.search(sent):
                cands.append(sent.rstrip("."))
    seen, out = set(), []
    for c in cands:
        k = c.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append({"id": f"r{len(out) + 1}", "text": c, "skills": [], "must_have": True})
        if len(out) >= max_n:
            break
    if not out and clean:
        out = [{"id": "r1", "text": clean[:300], "skills": [], "must_have": True}]
    return out
