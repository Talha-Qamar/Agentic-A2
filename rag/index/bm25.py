"""BM25 with a code-aware tokenizer that keeps library names like next.js, scikit-learn, c++ intact."""
from __future__ import annotations

import re

import numpy as np
from rank_bm25 import BM25Okapi

STOP = set("a an the and or of to in for on with by at from as is are was were be this that it its our your you we i my "
           "will can must should would have has had do does not need needs want looking experience".split())


def tokenize(text: str) -> list[str]:
    toks = re.findall(r"[a-z0-9][a-z0-9.+#/-]*[a-z0-9+#]|[a-z0-9]", text.lower())
    out = []
    for t in toks:
        if t in STOP:
            continue
        out.append(t)
        if any(ch in t for ch in ".-/"):
            out += [p for p in re.split(r"[.\-/]", t) if p and p not in STOP]
    return out


class BM25Index:
    def __init__(self, ids: list[str], texts: list[str]):
        self.ids = ids
        self.bm = BM25Okapi([tokenize(t) or ["_"] for t in texts])

    def search(self, query: str, k: int, mask: np.ndarray | None = None) -> list[tuple[str, float]]:
        s = np.asarray(self.bm.get_scores(tokenize(query)), dtype=np.float32)
        if mask is not None:
            s = np.where(mask, s, -1e9)
        k = min(k, len(self.ids))
        idx = np.argsort(-s)[:k]
        return [(self.ids[i], float(s[i])) for i in idx if s[i] > 0]
