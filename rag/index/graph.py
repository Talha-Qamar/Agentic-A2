"""Skill graph (V9 GraphRAG-style): skills, projects, client industries and outcomes as a graph.

Nodes: project/item ids, skills, industries, outcomes.  Edges come from chunk metadata:
item-HAS_SKILL->skill, item-FOR_INDUSTRY->industry, proposal-CITES->project, proposal-OUTCOME->outcome.
Answers "have I done X for a client in Y industry?" by walking skill->item(->industry) edges.
"""
from __future__ import annotations

from collections import defaultdict

from rag.ingest.lexicon import IMPORT_TO_SKILL


def canon(s: str) -> str:
    s = s.lower().strip()
    return {"postgres": "postgresql", "sklearn": "scikit-learn", "torch": "pytorch", "nextjs": "next.js",
            "node": "node.js", "k8s": "kubernetes"}.get(IMPORT_TO_SKILL.get(s, s), IMPORT_TO_SKILL.get(s, s))


class SkillGraph:
    def __init__(self, chunks: list[dict]):
        self.item_skills: dict[str, set[str]] = defaultdict(set)
        self.skill_items: dict[str, set[str]] = defaultdict(set)
        self.item_industry: dict[str, str] = {}
        self.item_chunks: dict[str, list[str]] = defaultdict(list)
        self.item_outcomes: dict[str, list[str]] = defaultdict(list)
        for c in chunks:
            item = c.get("project") or c.get("item_id")
            if not item:
                continue
            self.item_chunks[item].append(c["chunk_id"])
            for s in c.get("skills", []):
                cs = canon(s)
                self.item_skills[item].add(cs)
                self.skill_items[cs].add(item)
            if c.get("client_industry"):
                self.item_industry[item] = c["client_industry"]
            if c.get("type") == "proposal":
                for p in (c.get("extra") or {}).get("cited_projects", []):
                    self.item_outcomes[p].append(c.get("outcome") or "unknown")

    def items_for(self, skills: list[str], industry: str | None = None) -> list[tuple[str, float]]:
        scores: dict[str, float] = defaultdict(float)
        for s in skills:
            cs = canon(s)
            items = self.skill_items.get(cs, set())
            idf = 1.0 / (1 + len(items)) ** 0.5
            for it in items:
                scores[it] += idf
        if industry:
            for it in list(scores):
                if (self.item_industry.get(it) or "").lower() == industry.lower():
                    scores[it] += 0.5
        for it in scores:
            outs = self.item_outcomes.get(it, [])
            if outs:
                scores[it] += 0.1 * sum(o in ("won", "replied") for o in outs) / len(outs)
        return sorted(scores.items(), key=lambda x: -x[1])
