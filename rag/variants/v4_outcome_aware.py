"""V4 outcome-aware ranking: boost evidence from projects/proposals that won or got replies."""
from __future__ import annotations

from agent import settings
from rag.variants.base import minmax
from rag.variants.v3_rerank import V3Rerank


class V4OutcomeAware(V3Rerank):
    name = "v4_outcome_aware"

    def search_requirement(self, req, k):
        ranked = minmax(super().search_requirement(req, max(k, 15)))
        boost = settings.get("rag.outcome_boost", {"won": 0.25, "replied": 0.12, "ignored": -0.05})
        out = []
        for cid, s in ranked:
            c = self.corpus.by_id[cid]
            b = 0.0
            if c["type"] == "proposal":
                b += boost.get(c.get("outcome") or "", 0.0)
            wr = self.corpus.project_win_rate(c.get("project"))
            if wr is not None:
                b += boost["won"] * (wr - 0.5)
            out.append((cid, s + b))
        return sorted(out, key=lambda x: -x[1])[:k]
