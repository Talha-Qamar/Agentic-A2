"""Human evaluation sets and analysis.

    python -m evals.runners.human_eval build        # judge_items.json (30) + panel_pairs.json from real system outputs
    python -m evals.runners.human_eval analyse --url https://<app>   # pull anonymised votes/labels, compute agreement

Judge calibration: 30 proposals scored 1-10 by the student (/label) vs the LLM judge -> Spearman rho and quadratic
Cohen's kappa on 3 bins (1-4 weak, 5-7 ok, 8-10 strong). The judge is only trusted for the scored metric if kappa >= 0.4.
Panel: blind pairwise votes (/panel) -> win rate of GigBid vs each baseline with a two-sided sign test.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import random

from evals.runners.common import RESULTS, provenance, write_result


def build() -> None:
    from evals.runners.multiagent_comparison import judge
    cmp = json.loads((RESULTS / "multiagent_comparison.json").read_text())
    dev = {json.loads(line)["job_id"]: json.loads(line) for line in open(RESULTS.parent / "datasets" / "dev_set.jsonl")}
    letters = [r for r in cmp["rows"] if r.get("letter")]
    rng = random.Random(30)
    pick = rng.sample(letters, min(30, len(letters)))
    items = []
    for i, r in enumerate(pick):
        j = dev[r["job_id"]]
        items.append({"item_id": f"j{i:02d}", "system": r["system"], "job_id": r["job_id"], "job": f"{j['title']}\n\n{j['description']}",
                      "proposal": r["letter"], "judge": r.get("judge")})
    for it in items:
        if it["judge"] is None:
            it["judge"] = asyncio.run(judge(dev[it["job_id"]], it["proposal"]))
    write_result("judge_items.json", {"provenance": provenance(), "items": items})
    by_job: dict[str, dict] = {}
    for r in letters:
        by_job.setdefault(r["job_id"], {})[r["system"]] = r["letter"]
    pairs = []
    for jid, sy in by_job.items():
        for other in ("single_react", "supervisor"):
            if "gigbid_graph" in sy and other in sy:
                j = dev[jid]
                pairs.append({"pair_id": f"{jid}:{other}", "job": f"{j['title']}\n\n{j['description']}",
                              "a": {"system": "gigbid_graph", "text": sy["gigbid_graph"]}, "b": {"system": other, "text": sy[other]}})
    write_result("panel_pairs.json", {"provenance": provenance(), "items": pairs})
    print(f"{len(items)} judge items, {len(pairs)} panel pairs")


def analyse(url: str) -> None:
    import httpx
    from scipy.stats import binomtest, spearmanr
    from sklearn.metrics import cohen_kappa_score
    data = httpx.get(url.rstrip("/") + "/api/panel/export", timeout=60).json()
    items = {i["item_id"]: i for i in json.loads((RESULTS / "judge_items.json").read_text())["items"]}
    lab = [(items[x["item_id"]]["judge"], x["label"]) for x in data["labels"] if x["item_id"] in items and items[x["item_id"]]["judge"] is not None]
    out = {"n_labels": len(lab)}
    if len(lab) >= 5:
        j, h = zip(*lab)
        b = lambda v: 0 if v <= 4 else (1 if v <= 7 else 2)
        out.update(spearman=round(float(spearmanr(j, h).statistic), 4), kappa_quadratic=round(float(cohen_kappa_score([b(x) for x in h], [b(x) for x in j],
                   weights="quadratic")), 4), mean_judge=round(sum(j) / len(j), 2), mean_human=round(sum(h) / len(h), 2))
    pairs = {p["pair_id"]: p for p in json.loads((RESULTS / "panel_pairs.json").read_text())["items"]}
    panel = {}
    for other in ("single_react", "supervisor"):
        vs = [v for v in data["votes"] if pairs.get(v["pair_id"], {}).get("b", {}).get("system") == other]
        wins, losses = sum(v["choice"] == "a" for v in vs), sum(v["choice"] == "b" for v in vs)
        panel[other] = {"votes": len(vs), "gigbid_wins": wins, "baseline_wins": losses, "ties": len(vs) - wins - losses,
                        "raters": len({v["rater"] for v in vs}),
                        "p_value_sign_test": round(binomtest(wins, wins + losses).pvalue, 4) if wins + losses else None}
    out["panel"] = panel
    write_result("human_eval.json", {"provenance": provenance({"source": url}), "summary": out})
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "analyse"])
    ap.add_argument("--url", default="http://localhost:8000")
    a = ap.parse_args()
    build() if a.cmd == "build" else analyse(a.url)
