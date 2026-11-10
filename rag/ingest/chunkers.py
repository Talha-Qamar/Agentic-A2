"""Chunkers. `fixed` is the naive V0 baseline; `structured` respects document structure."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .loaders import Document


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    persona: str
    type: str
    source: str
    text: str
    title: str = ""
    item_id: str | None = None
    project: str | None = None
    repo: str | None = None
    date: str | None = None
    client_industry: str | None = None
    outcome: str | None = None
    skills: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    index: int = 0
    context: str = ""          # V6 contextual line (generated), prepended at embedding time when enabled

    def to_dict(self) -> dict:
        return asdict(self)

    def embed_text(self, contextual: bool = False) -> str:
        return (self.context + "\n" + self.text) if (contextual and self.context) else self.text


def _mk(doc: Document, text: str, i: int) -> Chunk:
    from .loaders import extract_skills
    return Chunk(chunk_id=f"{doc.doc_id}:{i}", doc_id=doc.doc_id, persona=doc.persona, type=doc.type, source=doc.source,
                 text=text.strip(), title=doc.title, item_id=doc.item_id, project=doc.project, repo=doc.repo, date=doc.date,
                 client_industry=doc.client_industry, outcome=doc.outcome,
                 skills=sorted(set(extract_skills(text)) | (set(doc.skills) if doc.type in ("proposal", "review") else set())),
                 extra=doc.extra, index=i)


def fixed(docs: list[Document], size: int = 900, overlap: int = 150) -> list[Chunk]:
    out = []
    for d in docs:
        t = d.text
        i, k = 0, 0
        while i < len(t):
            out.append(_mk(d, t[i: i + size], k))
            k += 1
            i += size - overlap
    return out


def _split_long(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for para in re.split(r"\n\s*\n", text):
        if len(cur) + len(para) > limit and cur:
            parts.append(cur)
            cur = para
        else:
            cur = (cur + "\n\n" + para) if cur else para
    if cur:
        parts.append(cur)
    return parts


def structured(docs: list[Document], limit: int = 1400) -> list[Chunk]:
    out: list[Chunk] = []
    for d in docs:
        pieces: list[str]
        if d.type in ("case_study", "readme"):
            secs = re.split(r"\n(?=##\s)", d.text)
            head = d.title
            pieces = []
            for s in secs:
                s = s if s.lstrip().startswith("#") or not head else s
                pieces += _split_long(s, limit)
            if len(d.text) <= limit:
                pieces = [d.text]
        elif d.type == "code":
            if len(d.text) <= limit:
                pieces = [d.text]
            else:
                pieces = [p for p in re.split(r"\n(?=(?:def |class |async def |export |function ))", d.text) if p.strip()]
        elif d.type == "cv":
            lines = [ln for ln in d.text.splitlines() if ln.strip()]
            pieces, cur = [], []
            for ln in lines:
                cur.append(ln)
                if len(" ".join(cur)) > 450:
                    pieces.append("\n".join(cur))
                    cur = []
            if cur:
                pieces.append("\n".join(cur))
        else:
            pieces = _split_long(d.text, limit)
        for i, p in enumerate(pieces):
            if p.strip():
                out.append(_mk(d, p, i))
    return out
