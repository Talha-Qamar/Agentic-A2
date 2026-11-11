"""X3: case studies built from a repo keep code-verified claims and lose invented ones before they are saved."""
import asyncio
from pathlib import Path

from agent.case_study_builder import build, repo_evidence, save, verify_against_code
from rag.embed import OverlapReranker

BASE = Path(__file__).resolve().parents[2] / "data/personas/ai_ml_engineer/repos/triage-agent"
FILES = {str(f.relative_to(BASE)): f.read_text() for f in BASE.rglob("*") if f.is_file()}


def test_invented_claims_are_removed_code_claims_kept():
    draft = ("Action: I implemented it with Celery, Redis and LangChain workers.\n\n"
             "Result: I cut cloud costs by 73% for a Fortune 500 bank using Kubernetes and Terraform.")
    clean, checks = verify_against_code(draft, repo_evidence("triage-agent", FILES), OverlapReranker().score)
    verdicts = {c.text[:7]: c.verdict for c in checks}
    assert verdicts["Action:"] == "supported"
    assert verdicts["Result:"] == "unsupported"
    assert "73%" not in clean and "Celery" in clean


def test_build_and_save_feeds_portfolio(tmp_path):
    r = asyncio.run(build("triage-agent", FILES, use_llm=False, score_fn=OverlapReranker().score))
    assert r["verification"]["unsupported"] == 0 and "celery" in r["skills"]
    p = save(r, tmp_path)
    assert p.read_text().startswith("---\nrepo: triage-agent")
