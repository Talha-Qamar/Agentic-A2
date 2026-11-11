"""Intake + Job Analyst."""
from __future__ import annotations

from agent.guardrails import detect_injection, quarantine, wrap_untrusted
from agent.handoffs import JobPost, JobSpec, Requirement
from agent.llm import complete_json, load_prompt
from agent.nodes.runtime import Deps, node
from rag.requirements import extract_requirements


def job_text(job: dict) -> str:
    return f"{job.get('title', '')}\n\n{job.get('description', '')}"


@node("intake", retries=1)
async def intake(state: dict, deps: Deps) -> dict:
    """Load the job through the marketplace port (if only an id was given) and screen it for injected instructions."""
    job = state.get("job") or {}
    if job.get("job_id") and not job.get("description"):
        job = await deps.call("scout", "get_job", {"job_id": job["job_id"]})
    job = JobPost(**{k: v for k, v in job.items() if k in JobPost.model_fields}).model_dump()
    text = job_text(job)
    inj = detect_injection(text) if deps.defences.get("detect", True) else {"detected": False, "hits": [], "score": 0}
    clean, removed = quarantine(text) if (deps.defences.get("detect", True) and inj["detected"]) else (text, [])
    return {"job": job, "job_clean_text": clean, "status": "analysing",
            "risk": {"injection_detected": inj["detected"], "injection_hits": [h["label"] for h in inj["hits"]], "quarantined_spans": removed}}


async def _fallback(state: dict, deps: Deps, err: Exception) -> dict:
    job = state["job"]
    reqs = extract_requirements(state.get("job_clean_text") or job_text(job))
    spec = JobSpec(summary=job["title"], requirements=[Requirement(**r) for r in reqs], budget_type=job.get("budget_type", "fixed"),
                   budget_min=job.get("budget_min"), budget_max=job.get("budget_max"), timeline_days=job.get("duration_days"),
                   screening_questions=job.get("screening_questions", []), category=job.get("category"))
    return {"job_spec": spec.model_dump() | {"degraded": f"LLM unavailable: {str(err)[:120]}"}}


@node("analyst", fallback=_fallback, retries=1)
async def analyst(state: dict, deps: Deps) -> dict:
    job = state["job"]
    text = state.get("job_clean_text") or job_text(job)
    body = wrap_untrusted(text) if deps.defences.get("delimit", True) else text
    user = (f"Category: {job.get('category')}\nBudget type: {job.get('budget_type')} min={job.get('budget_min')} "
            f"max={job.get('budget_max')}\nDuration days: {job.get('duration_days')}\n"
            f"Screening questions: {job.get('screening_questions')}\n\nJob post:\n{body}")
    spec = await complete_json("analyst", load_prompt("analyst"), user, JobSpec)
    for i, r in enumerate(spec.requirements):
        r.id = f"r{i + 1}"
    spec.budget_type = job.get("budget_type", spec.budget_type)
    spec.budget_max = job.get("budget_max") or spec.budget_max
    spec.budget_min = job.get("budget_min") or spec.budget_min
    spec.screening_questions = job.get("screening_questions") or spec.screening_questions
    spec.category = job.get("category") or spec.category
    return {"job_spec": spec.model_dump()}
