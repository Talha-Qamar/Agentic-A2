"""Structured hand-offs between agents (C3). Anything a later step decides on is one of these."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class JobPost(BaseModel):
    """Raw job as returned by the marketplace port. Title/description are UNTRUSTED text."""
    job_id: str
    title: str
    description: str
    category: str | None = None
    skills: list[str] = []
    budget_type: Literal["fixed", "hourly"] = "fixed"
    budget_min: float | None = None
    budget_max: float | None = None
    duration_days: int | None = None
    screening_questions: list[str] = []
    client_id: str | None = None
    connects_cost: int | None = None
    posted_minute: float | None = None
    source: str = "gigsim"


class Requirement(BaseModel):
    id: str
    text: str = Field(description="one concrete thing the client needs")
    skills: list[str] = Field(default_factory=list, description="tools/skills this requirement implies, named canonically")
    must_have: bool = True


class JobSpec(BaseModel):
    summary: str = ""
    deliverables: list[str] = []
    requirements: list[Requirement] = []
    skills: list[str] = []
    budget_type: Literal["fixed", "hourly"] = "fixed"
    budget_min: float | None = None
    budget_max: float | None = None
    timeline_days: int | None = None
    screening_questions: list[str] = []
    hidden_needs: list[str] = Field(default_factory=list, description="needs implied but not stated")
    category: str | None = None


class RiskFlag(BaseModel):
    type: Literal["off_platform", "free_work", "credentials", "payment_scam", "too_good_to_be_true", "low_quality_client",
                  "injection", "low_budget", "unverified_payment", "other"]
    evidence: str
    severity: Literal["low", "medium", "high"] = "medium"


class RiskReport(BaseModel):
    client_quality: float = Field(0.5, ge=0, le=1)
    scam_score: float = Field(0.0, ge=0, le=1)
    risk_score: float = Field(0.0, ge=0, le=1)
    flags: list[RiskFlag] = []
    injection_detected: bool = False
    injection_hits: list[str] = []
    quarantined_spans: list[str] = []
    recommendation: Literal["ok", "caution", "avoid"] = "ok"
    reasons: list[str] = []


class EvidenceItem(BaseModel):
    evidence_id: str
    item_id: str | None = None          # project id (or proposal id) the chunk proves
    type: str                            # case_study | readme | code | cv | review | proposal
    source: str
    title: str = ""
    date: str | None = None
    outcome: str | None = None
    text: str
    score: float = 0.0
    skills: list[str] = []


class RequirementMatch(BaseModel):
    requirement_id: str
    requirement: str
    evidence_ids: list[str] = []
    support: Literal["strong", "partial", "none"] = "none"
    score: float = 0.0


class FitReport(BaseModel):
    fit_score: float = Field(0.0, ge=0, le=1)
    coverage: float = Field(0.0, ge=0, le=1)
    matches: list[RequirementMatch] = []
    strengths: list[str] = []
    gaps: list[str] = []
    reasons: list[str] = []


class BidDecision(BaseModel):
    action: Literal["bid", "watch", "skip"]
    confidence: float = 0.5
    reasons: list[str] = []
    rule_trace: list[str] = []
    auto_skipped: bool = False


class PriceQuote(BaseModel):
    bid_type: Literal["fixed", "hourly"]
    amount: float
    currency: str = "USD"
    floor: float
    market: dict = {}
    client_budget_max: float | None = None
    connects_cost: int = 0
    connects_usd: float = 0.0
    p_reply_estimate: float = 0.0
    expected_value_usd: float = 0.0
    worth_connects: bool = True
    rationale: str = ""


class Claim(BaseModel):
    id: str
    text: str
    evidence_ids: list[str] = []
    verdict: Literal["supported", "partial", "unsupported", "unchecked"] = "unchecked"
    score: float = 0.0
    note: str = ""


class ScreeningAnswer(BaseModel):
    question: str
    answer: str
    evidence_ids: list[str] = []


class ProposalDraft(BaseModel):
    version: int = 1
    cover_letter: str
    screening_answers: list[ScreeningAnswer] = []
    claims: list[Claim] = []
    evidence_ids: list[str] = []
    word_count: int = 0
    unsupported_before: int = 0
    unsupported_after: int = 0
    removed_claims: list[str] = []


class CritiqueIssue(BaseModel):
    type: Literal["grounding", "generic_opening", "personalisation", "length", "missing_requirement", "tone", "screening", "other"]
    detail: str


class Critique(BaseModel):
    approved: bool
    score: float = Field(0, ge=0, le=10)
    issues: list[CritiqueIssue] = []
    instructions: str = ""
    revision: int = 0


class Violation(BaseModel):
    rule: str
    evidence: str
    span: str = ""


class ComplianceVerdict(BaseModel):
    allowed: bool
    blocked_reason: str | None = None
    violations: list[Violation] = []
    fixes_applied: list[str] = []
    final_text: str = ""


class ApprovalDecision(BaseModel):
    action: Literal["approve", "edit", "reject"]
    edited_text: str | None = None
    reason: str | None = None
    approver: str | None = None


class SubmissionResult(BaseModel):
    proposal_id: str | None = None
    status: str
    connects_spent: int = 0
    idempotency_key: str
    replay: bool = False
    error: str | None = None


# ------------------------------------------------------------------ conversation graph
class IntentResult(BaseModel):
    intent: Literal["question", "negotiation", "interview_request", "scam_signal", "other"]
    confidence: float = 0.5
    summary: str = ""
    injection_detected: bool = False


class ReplyDraft(BaseModel):
    text: str
    proposed_slots: list[dict] = []
    evidence_ids: list[str] = []
    counter_offer: float | None = None
    notes: list[str] = []
