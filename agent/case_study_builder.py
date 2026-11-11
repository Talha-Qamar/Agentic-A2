"""Extension X3 - GitHub repo -> verified case study -> Portfolio server.

1. Fetch: repo README + code through the GitHub MCP server (`rag/ingest/github_mcp.py`) or a local checkout.
2. Draft: the LLM writes a STAR case study from the repo text only (`agent/prompts/case_study_builder.md`); without a
   model (tests, eval baseline) a deterministic draft is assembled from README sentences and code-level skills.
3. Verify against the code: the draft is split into claims (rag/verify.py) and each claim is checked against chunks
   of THAT repo only (BM25 candidates -> cross-encoder support + number/entity checks). Unsupported sentences are
   deleted before anything is saved; the verification summary is written into the front matter.
4. Feed the Portfolio server: the result is saved into the user's portfolio `case_studies/`, so the next
   `search_evidence` / `match_requirements` call re-indexes that user's collection and can cite it.
"""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from rag import verify as V
from rag.index.bm25 import BM25Index
from rag.ingest.loaders import extract_skills

GENERIC = {"python", "json", "yaml", "bash", "pip", "api", "rest api", "worker", "llm", "agents"}


def repo_evidence(repo: str, files: dict[str, str]) -> list[dict]:
    """Small evidence units: README paragraphs and ~40-line code windows, each with a stable evidence_id."""
    ev = []
    for rel, text in sorted(files.items()):
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        if rel.lower().endswith("readme.md"):
            parts = [p.strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 20]
        else:
            lines = text.splitlines()
            parts = ["\n".join(lines[i:i + 40]) for i in range(0, len(lines), 40)]
        for i, p in enumerate(parts):
            ev.append({"evidence_id": f"{repo}:{rel}#{i}", "source": rel, "text": f"{rel}\n{p}"})
    return ev


def code_skills(files: dict[str, str], repo: str = "") -> list[str]:
    repo_words = {repo.lower(), *repo.lower().split("-")}
    seen: dict[str, int] = {}
    for rel, t in files.items():
        if not rel.lower().endswith("readme.md"):
            for s in extract_skills(t):
                seen[s] = seen.get(s, 0) + 1
    return [s for s, _ in sorted(seen.items(), key=lambda x: -x[1]) if s.lower() not in GENERIC and s.lower() not in repo_words]


def deterministic_draft(repo: str, files: dict[str, str]) -> dict:
    readme = next((t for r, t in files.items() if r.lower().endswith("readme.md")), "")
    body = re.sub(r"<!--.*?-->", "", readme, flags=re.S)
    title = (re.search(r"^#\s+(.+)$", body, re.M) or [None, repo])[1].strip()
    sents = [s for s in V.split_sentences(re.sub(r"^#.*$", "", body, flags=re.M)) if len(s) > 30]
    skills = code_skills(files, repo)
    result = next((s for s in sents if re.search(r"\d", s) and not re.match(r"(?i)\W*stack", s)), None)
    md = (f"Situation: {sents[0] if sents else 'Repository ' + repo + '.'}\n\n"
          f"Task: build and ship {title}.\n\n"
          f"Action: I implemented it with {', '.join(skills[:6]) or 'the code in this repository'} "
          f"(see {', '.join(sorted(r for r in files if not r.lower().endswith('readme.md'))[:3])}).\n\n"
          f"Result: {result or 'not stated in the repository.'}")
    return {"title": title, "markdown": md, "skills": skills[:8]}


async def llm_draft(repo: str, files: dict[str, str]) -> dict:
    from agent.guardrails import wrap_untrusted
    from agent.llm import complete, load_prompt, parse_json
    text = "\n\n".join(f"### {r}\n{t[:2500]}" for r, t in sorted(files.items(), key=lambda x: (not x[0].lower().endswith("readme.md"), x[0])))[:12000]
    out = parse_json(await complete("writer", load_prompt("case_study_builder"),
                                    f"Repository: {repo}\n\nREPOSITORY TEXT:\n{wrap_untrusted(text, 'repository')}", json_mode=True))
    return {"title": out.get("title") or repo, "markdown": out.get("markdown") or "", "skills": out.get("skills") or code_skills(files, repo)[:8]}


def verify_against_code(markdown: str, evidence: list[dict], score_fn=None) -> tuple[str, list[V.ClaimCheck]]:
    if score_fn is None:
        from agent.nodes.verifier import _score_fn
        score_fn = _score_fn()
    bm = BM25Index([e["evidence_id"] for e in evidence], [e["text"] for e in evidence])
    by_id = {e["evidence_id"]: e for e in evidence}

    def search(q: str, k: int):
        return [by_id[i] for i, _ in bm.search(q, k)]
    checks = V.verify_text(markdown, search, score_fn)
    for c in checks:
        code_verify(c, evidence)
    clean, _ = V.remove_unsupported(markdown, checks)
    return clean, checks


def code_verify(c: V.ClaimCheck, evidence: list[dict]) -> None:
    """A claim naming libraries/techniques is supported by the code itself when every named skill occurs in a code
    file of this repo (imports, requirements, identifiers) - the case a prose-trained cross-encoder scores low."""
    skills = [s for s in extract_skills(c.text) if s.lower() not in GENERIC]
    if len(skills) < 2 or c.missing_numbers:
        return
    code = [e for e in evidence if not e["source"].lower().endswith("readme.md")]
    hits = {s: [e["evidence_id"] for e in code if s.lower() in e["text"].lower()] for s in skills}
    if all(hits.values()):
        c.verdict, c.note = "supported", "code-verified: " + ", ".join(skills)
        c.evidence_ids = sorted({i for v in hits.values() for i in v[:1]})
        c.missing_entities = []
    elif c.verdict == "supported":
        c.verdict, c.note = "partial", "not in code: " + ", ".join(s for s, v in hits.items() if not v)


async def build(repo: str, files: dict[str, str], *, use_llm: bool = True, source: str = "local", score_fn=None) -> dict:
    draft = await llm_draft(repo, files) if use_llm else None
    if not draft or len(V.split_claims(draft["markdown"])) == 0:   # no model, or a reply with nothing checkable
        draft = deterministic_draft(repo, files)
    ev = repo_evidence(repo, files)
    before = draft["markdown"]
    clean, checks = verify_against_code(before, ev, score_fn)
    summ = V.summary(checks)
    fm = (f"---\nrepo: {repo}\nsource: {source}\nbuilder: x3-portfolio-builder\ngenerated: {dt.date.today().isoformat()}\n"
          f"verified_claims: {summ['claims']}\nremoved_unsupported: {summ['unsupported']}\nskills: [{', '.join(draft['skills'])}]\n---\n")
    return {"repo": repo, "title": draft["title"], "draft": before, "markdown": fm + f"# Case study: {draft['title']}\n\n" + clean,
            "verification": summ, "checks": V.to_dicts(checks), "skills": draft["skills"]}


def save(result: dict, portfolio_dir: Path) -> Path:
    p = Path(portfolio_dir) / "case_studies" / f"builder-{result['repo']}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(result["markdown"])
    return p
