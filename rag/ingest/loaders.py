"""Loaders: PDF CVs, Markdown case studies, repo READMEs and code, reviews, past proposals.

Every document carries metadata: persona, type, project/item, skills, date, client industry
and, for proposals, outcome.  Repos can be loaded from disk or through the GitHub MCP server
(rag/ingest/github_mcp.py) - both produce the same Document objects.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .lexicon import IMPORT_TO_SKILL, PHRASES, TERMS

CODE_EXT = {".py", ".ts", ".tsx", ".js", ".sql", ".yml", ".yaml", ".toml"}


@dataclass
class Document:
    doc_id: str
    persona: str
    type: str                 # case_study | readme | code | cv | review | proposal
    source: str               # path relative to the persona dir (or github://owner/repo/path)
    text: str
    title: str = ""
    item_id: str | None = None    # project id, repo:<slug>, or proposal id
    project: str | None = None    # resolved project id when known (case-study front matter / link)
    repo: str | None = None
    date: str | None = None
    client_industry: str | None = None
    outcome: str | None = None
    skills: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _id(*parts) -> str:
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:12]


def extract_skills(text: str) -> list[str]:
    t = " " + re.sub(r"\s+", " ", text.lower()) + " "
    found = set()
    for p in PHRASES:
        if p in t:
            found.add(p)
    for term in TERMS:
        if len(term) < 2 or " " in term:
            continue
        if re.search(rf"(?<![\w.@/-]){re.escape(term)}(?![\w-])", t):
            found.add(term)
    for m in re.finditer(r"^\s*(?:from|import)\s+([\w.@/-]+)", text, re.M):
        mod = m.group(1).split(".")[0]
        found.add(IMPORT_TO_SKILL.get(mod, mod.replace("_", "-")))
    for m in re.finditer(r'from\s+"([^"]+)"', text):
        found.add(IMPORT_TO_SKILL.get(m.group(1), m.group(1).lstrip("@").split("/")[0]))
    return sorted(found)


def _front_matter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, text[m.end():]


def _strip_banner(text: str) -> str:
    return re.sub(r"<!--\s*SYNTHETIC DATA.*?-->\s*", "", text, flags=re.S)


def load_pdf(path: Path) -> str:
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)


def load_persona_dir(base: Path, persona: str, include_repos: bool = True) -> list[Document]:
    base = Path(base)
    docs: list[Document] = []
    repo_to_project: dict[str, str] = {}
    for p in sorted((base / "case_studies").glob("*.md")):
        meta, body = _front_matter(p.read_text())
        body = _strip_banner(body)
        title = (re.search(r"^#\s+(.+)$", body, re.M) or re.search(r"(.+)", body)).group(1)
        proj = meta.get("project")
        if meta.get("repo"):
            repo_to_project[meta["repo"]] = proj
        docs.append(Document(_id(persona, p.name), persona, "case_study", f"case_studies/{p.name}", body.strip(), title=title,
                             item_id=proj, project=proj, repo=meta.get("repo"), date=meta.get("date"),
                             client_industry=meta.get("client_industry"), skills=extract_skills(body)))
    if include_repos and (base / "repos").exists():
        for rdir in sorted((base / "repos").iterdir()):
            docs += load_repo_files(persona, rdir.name, {str(f.relative_to(rdir)): f.read_text(errors="ignore")
                                                          for f in rdir.rglob("*") if f.is_file()},
                                    repo_to_project.get(rdir.name), source_prefix=f"repos/{rdir.name}")
    cv = base / "cv.pdf"
    if cv.exists():
        docs.append(Document(_id(persona, "cv"), persona, "cv", "cv.pdf", load_pdf(cv), title="CV", skills=[]))
        docs[-1].skills = extract_skills(docs[-1].text)
    rv = base / "reviews.json"
    if rv.exists():
        for r in json.loads(rv.read_text()):
            docs.append(Document(_id(persona, r["review_id"]), persona, "review", f"reviews.json#{r['review_id']}",
                                 f"Client review from {r['client']} ({r['industry']}), {r['rating']} stars: {r['text']}",
                                 title=f"Review: {r['client']}", item_id=r.get("project"), project=r.get("project"),
                                 date=r.get("date"), client_industry=r.get("industry"), skills=extract_skills(r["text"])))
    pp = base / "past_proposals.jsonl"
    if pp.exists():
        for line in pp.read_text().splitlines():
            r = json.loads(line)
            docs.append(Document(_id(persona, r["proposal_id"]), persona, "proposal", f"past_proposals.jsonl#{r['proposal_id']}",
                                 r["text"], title=r["job_title"], item_id=r["proposal_id"], date=r["date"],
                                 outcome=r["outcome"], skills=extract_skills(r["text"] + " " + " ".join(r["job_requirements"])),
                                 extra={"cited_projects": r.get("cited_projects", []), "job_category": r.get("job_category"),
                                        "opening_style": r.get("opening_style"), "job_requirements": r.get("job_requirements", [])}))
    return docs


def load_repo_files(persona: str, repo: str, files: dict[str, str], project: str | None, source_prefix: str) -> list[Document]:
    docs = []
    for rel, text in sorted(files.items()):
        suffix = Path(rel).suffix
        if rel.lower().endswith("readme.md"):
            body = _strip_banner(text)
            docs.append(Document(_id(persona, repo, rel), persona, "readme", f"{source_prefix}/{rel}", body.strip(),
                                 title=f"{repo} README", item_id=project or f"repo:{repo}", project=project, repo=repo,
                                 skills=extract_skills(body)))
        elif suffix in CODE_EXT or rel.endswith(("requirements.txt", "package.json")):
            docs.append(Document(_id(persona, repo, rel), persona, "code", f"{source_prefix}/{rel}", text,
                                 title=f"{repo}/{rel}", item_id=project or f"repo:{repo}", project=project, repo=repo,
                                 skills=extract_skills(text)))
    return docs
