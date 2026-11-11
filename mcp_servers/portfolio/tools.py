"""Portfolio tools (read-only). Schemas are Pydantic models, so hosts receive input and output schemas."""
from __future__ import annotations

from typing import Literal

from mcp.server.fastmcp import Context
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)

DocType = Literal["case_study", "readme", "code", "cv", "review", "proposal"]


class EvidenceFilters(BaseModel):
    types: list[DocType] | None = Field(None, description="only these evidence types")
    outcomes: list[Literal["won", "replied", "ignored"]] | None = Field(None, description="for past proposals: only these outcomes")
    since: str | None = Field(None, pattern=r"^\d{4}(-\d{2})?(-\d{2})?$", description="ISO date lower bound, e.g. 2024-06")
    project: str | None = Field(None, max_length=80)


class EvidenceOut(BaseModel):
    evidence_id: str
    type: str
    source: str
    title: str = ""
    date: str | None = None
    outcome: str | None = None
    project: str | None = None
    text: str
    score: float


class SearchEvidenceResult(BaseModel):
    requirement: str
    items: list[EvidenceOut]


class RequirementIn(BaseModel):
    id: str = Field(max_length=16)
    text: str = Field(min_length=3, max_length=400)


class MatchResult(BaseModel):
    variant: str
    per_requirement: dict[str, list[EvidenceOut]]
    unsupported_requirements: list[str]
    items: list[EvidenceOut]


class CaseStudy(BaseModel):
    id: str
    title: str | None = None
    text: str
    date: str | None = None
    client_industry: str | None = None
    source: str
    repo: str | None = None


class SkillCount(BaseModel):
    skill: str
    mentions: int
    example_item: str | None = None


class SkillList(BaseModel):
    skills: list[SkillCount]


def _user(ctx: Context | None) -> str | None:
    try:
        req = ctx.request_context.request
        return req.headers.get("x-gigbid-user") if req is not None else None
    except Exception:  # noqa: BLE001
        return None


def _ev(d: dict) -> EvidenceOut:
    return EvidenceOut(**{k: d.get(k) for k in EvidenceOut.model_fields if k in d or k in ("title", "date", "outcome", "project")}
                       | {"text": d.get("text", ""), "score": float(d.get("score", 0.0)), "type": d.get("type", ""),
                          "source": d.get("source", ""), "evidence_id": d["evidence_id"]})


def register(mcp, backend) -> None:
    @mcp.tool(annotations=READ_ONLY, title="Search portfolio evidence")
    def search_evidence(requirement: str = Field(min_length=3, max_length=500, description="one client requirement, in plain words"),
                        k: int = Field(5, ge=1, le=20), filters: EvidenceFilters | None = None,
                        ctx: Context = None) -> SearchEvidenceResult:
        """Find portfolio evidence (case studies, repos, code, reviews, CV lines, past proposals with outcomes) that
        proves the freelancer can meet ONE requirement. Returns items with type, source, date and outcome."""
        items = backend.search(requirement, k, filters.model_dump(exclude_none=True) if filters else None, _user(ctx))
        return SearchEvidenceResult(requirement=requirement, items=[_ev(i) for i in items])

    @mcp.tool(annotations=READ_ONLY, title="Match job requirements to evidence")
    def match_requirements(job_text: str = Field(min_length=10, max_length=12000, description="the job post (untrusted text)"),
                           requirements: list[RequirementIn] = Field(default_factory=list, max_length=12),
                           k: int = Field(5, ge=1, le=15), ctx: Context = None) -> MatchResult:
        """Map every requirement of a job to supporting portfolio evidence in one call (requirement decomposition).
        If no requirements are given they are extracted from the job text. Requirements with no adequate evidence are
        listed in unsupported_requirements - do not claim them."""
        if not hasattr(backend, "match"):
            reqs = [r.model_dump() for r in requirements] or [{"id": "r1", "text": job_text[:400]}]
            per = {r["id"]: [_ev(i) for i in backend.search(r["text"], k, None, _user(ctx))] for r in reqs}
            flat = [e for lst in per.values() for e in lst]
            return MatchResult(variant="standalone-hybrid", per_requirement=per, unsupported_requirements=[], items=flat)
        out = backend.match(job_text, [r.model_dump() | {"skills": []} for r in requirements], k, _user(ctx))
        return MatchResult(variant=out["variant"], per_requirement={k_: [_ev(e) for e in v] for k_, v in out["per_requirement"].items()},
                           unsupported_requirements=out["unsupported_requirements"], items=[_ev(e) for e in out["items"]])

    @mcp.tool(annotations=READ_ONLY, title="Get a case study")
    def get_case_study(id: str = Field(min_length=1, max_length=80, description="case-study or project id"),
                       ctx: Context = None) -> CaseStudy:
        """Return the full text and metadata of one case study."""
        c = backend.get_case(id, _user(ctx))
        if not c:
            raise ValueError(f"case study {id!r} not found")
        return CaseStudy(**c)

    @mcp.tool(annotations=READ_ONLY, title="List skills")
    def list_skills(ctx: Context = None) -> SkillList:
        """List the skills evidenced anywhere in the portfolio, with how often each appears and an example item."""
        return SkillList(skills=[SkillCount(**s) for s in backend.list_skills(_user(ctx))])
