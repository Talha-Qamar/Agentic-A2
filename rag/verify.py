"""Claim splitting and grounding (B3).

verify_text(text, search_fn, ...) splits a proposal into experience claims and checks each against
retrieved portfolio evidence:

* semantic support  - max cross-encoder probability over candidate evidence (cited + re-retrieved);
* number check      - every figure in the claim (41%, 9.2 h, 2.3x) must appear in the supporting evidence;
* entity check      - capitalised names (clients, tools) must appear in the supporting evidence;
* optional LLM judge for borderline claims.

Verdicts: supported | partial | unsupported.  remove_unsupported() deletes unsupported sentences so
the Critic only ever sees grounded drafts; the rate before and after is recorded on the draft.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Callable

from agent import settings

CLAIM_HINT = re.compile(
    r"(?i)\b(i (built|delivered|designed|shipped|led|created|developed|implemented|worked|migrated|reduced|improved|"
    r"trained|deployed|automated|rebuilt|wrote|cut|helped|ran|have|did|made|fixed|launched|integrated)|my (work|project|"
    r"experience|client|team)|at [A-Z][\w.&-]+|for (a|an) [\w-]+ client|years? of experience|previously|last year|"
    r"in production|result(ed)?|reduc|increas|improv|\d+(\.\d+)?\s?(%|x|ms|s\b|h\b|hours|minutes|days|weeks|k\b|m\b))")
NOT_CLAIM = re.compile(r"(?i)^(my plan|plan:|i (can|will|would|could|am happy|'d|look forward)|happy to|looking forward|"
                       r"(do|would|could|can) you|thanks|best|regards|drafted with ai|let me know|\(\d\))")
NUM = re.compile(r"\d+(?:[.,]\d+)?\s?(?:%|x\b|k\b|m\b|ms\b|s\b|h\b)?")
CAP = re.compile(r"\b[A-Z][a-zA-Z0-9.+&-]{2,}(?:\s[A-Z][a-zA-Z0-9.+&-]{2,})*")
COMMON_CAPS = {"I", "My", "The", "This", "That", "Your", "You", "We", "Our", "At", "In", "For", "With", "And", "Hi", "Hello",
               "Last", "When", "After", "Before", "Also", "Then", "Over", "Using", "Built", "Drafted", "AI", "API", "Happy",
               "Previously", "Each", "Every", "Most", "On", "It", "As", "If", "Here", "There", "Both", "One", "Two", "Three"}


@dataclass
class ClaimCheck:
    id: str
    text: str
    verdict: str = "unchecked"
    score: float = 0.0
    evidence_ids: list[str] = field(default_factory=list)
    missing_numbers: list[str] = field(default_factory=list)
    missing_entities: list[str] = field(default_factory=list)
    note: str = ""


def split_sentences(text: str) -> list[str]:
    parts = []
    for para in re.split(r"\n\s*\n|\n(?=[-*•]\s)", text or ""):
        para = para.strip().lstrip("-*• ").strip()
        if not para:
            continue
        parts += [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(\"'])", para) if s.strip()]
    return parts


def split_claims(text: str) -> list[str]:
    return [s for s in split_sentences(text) if CLAIM_HINT.search(s) and not NOT_CLAIM.search(s) and len(s) > 25]


def _norm_num(s: str) -> str:
    return re.sub(r"\s", "", s.lower()).replace(",", "")


def _numbers(s: str) -> list[str]:
    return [_norm_num(n) for n in NUM.findall(s) if re.search(r"\d", n) and not re.fullmatch(r"20\d\d", n.strip())]


def _entities(s: str) -> list[str]:
    ents = []
    for m in CAP.finditer(s):
        w = m.group(0)
        first = w.split()[0]
        if first in COMMON_CAPS or w in COMMON_CAPS:
            continue
        if m.start() == 0 or s[m.start() - 2: m.start()].strip() in (".", "!", "?"):
            # sentence-initial capital: only treat as entity if it is not a common word
            if w.lower() in ("over", "using", "after", "before", "each"):
                continue
        ents.append(w)
    return ents


def _sig(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def check_claim(cid: str, claim: str, candidates: list[dict], score_fn: Callable[[str, list[str]], list[float]],
                llm_judge: Callable[[str, list[dict]], str] | None = None) -> ClaimCheck:
    cc = ClaimCheck(cid, claim)
    if not candidates:
        cc.verdict, cc.note = "unsupported", "no evidence retrieved"
        return cc
    texts = [c["text"] for c in candidates]
    raw = score_fn(claim, texts)
    probs = [(_sig(s) if (s > 1.0 or s < 0.0) else s) for s in raw]
    order = sorted(range(len(candidates)), key=lambda i: -probs[i])
    best = order[0]
    cc.score = round(probs[best], 4)
    top = [candidates[i] for i in order[:3] if probs[i] >= settings.get("verification.partial_threshold", 0.45) * 0.8]
    cc.evidence_ids = [c["evidence_id"] for c in top] or [candidates[best]["evidence_id"]]
    pool = " ".join(c["text"] for c in (top or [candidates[best]])).lower()
    pool_nums = {_norm_num(n) for n in NUM.findall(pool)}
    cc.missing_numbers = [n for n in _numbers(claim) if n not in pool_nums and n.rstrip("%xkmsh") not in pool]
    cc.missing_entities = [e for e in _entities(claim) if e.lower() not in pool]
    sup, part = settings.get("verification.support_threshold", 0.62), settings.get("verification.partial_threshold", 0.45)
    if cc.score >= sup and not cc.missing_numbers and len(cc.missing_entities) <= 0:
        cc.verdict = "supported"
    elif cc.score >= part and not cc.missing_numbers:
        cc.verdict = "partial"
    elif cc.score >= sup and cc.missing_numbers:
        cc.verdict = "partial"
        cc.note = "figures not found in evidence: " + ", ".join(cc.missing_numbers)
    else:
        cc.verdict = "unsupported"
    if llm_judge and cc.verdict == "partial":
        v = llm_judge(claim, top or [candidates[best]])
        if v in ("supported", "partial", "unsupported"):
            cc.note = (cc.note + f" | judge: {v}").strip(" |")
            cc.verdict = v
    if cc.missing_numbers and cc.verdict == "supported":
        cc.verdict = "partial"
    return cc


def verify_text(text: str, search_fn: Callable[[str, int], list[dict]], score_fn, cited: list[dict] | None = None,
                llm_judge=None) -> list[ClaimCheck]:
    out = []
    for i, claim in enumerate(split_claims(text)):
        cands = {c["evidence_id"]: c for c in (cited or [])}
        for c in search_fn(claim, 6):
            cands.setdefault(c["evidence_id"], c)
        out.append(check_claim(f"c{i + 1}", claim, list(cands.values()), score_fn, llm_judge))
    return out


def remove_unsupported(text: str, checks: list[ClaimCheck]) -> tuple[str, list[str]]:
    bad = [c.text for c in checks if c.verdict == "unsupported"]
    if not bad:
        return text, []
    paras = re.split(r"(\n\s*\n)", text)
    out = []
    for p in paras:
        if p.strip() == "":
            out.append(p)
            continue
        sents = re.split(r"(?<=[.!?])\s+(?=[A-Z(\"'])", p)
        kept = [s for s in sents if s.strip() not in bad]
        out.append(" ".join(kept))
    clean = re.sub(r"\n{3,}", "\n\n", "".join(out)).strip()
    return clean, bad


def summary(checks: list[ClaimCheck]) -> dict:
    n = len(checks)
    c = {v: sum(x.verdict == v for x in checks) for v in ("supported", "partial", "unsupported")}
    return {"claims": n, **c, "unsupported_rate": round(c["unsupported"] / n, 4) if n else 0.0}


def to_dicts(checks: list[ClaimCheck]) -> list[dict]:
    return [asdict(c) for c in checks]
