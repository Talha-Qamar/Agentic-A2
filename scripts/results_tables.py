"""Regenerate every results table from evals/results/*.json (README, report). Missing files print as "pending".

    python scripts/results_tables.py            # markdown to stdout
    python scripts/results_tables.py --json     # the same numbers as JSON (used by the report builder)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[1] / "evals" / "results"


def load(name: str):
    p = R / name
    return json.loads(p.read_text()) if p.exists() else None


def f(x, nd=3):
    return "-" if x is None else (f"{x:.{nd}f}" if isinstance(x, float) else str(x))


def rag_table() -> str:
    d = load("rag_benchmark.json")
    if not d:
        return "_rag_benchmark.json pending_\n"
    out = ["| variant | Recall@5 | capped R@5 | MRR | nDCG@10 | p95 latency (s) | R@5 ai_ml | R@5 data | R@5 fullstack |", "|---|---|---|---|---|---|---|---|---|"]
    for v, s in d["summary"].items():
        o, bp = s["overall"], s["by_persona"]
        out.append(f"| {v} | {f(o['recall@5'])} | {f(o['capped_recall@5'])} | {f(o['mrr'])} | {f(o['ndcg@10'])} | {f(o['p95_latency_s'])} | "
                   f"{f(bp['ai_ml_engineer']['recall@5'])} | {f(bp['data_analyst']['recall@5'])} | {f(bp['fullstack_web_dev']['recall@5'])} |")
    return "\n".join(out) + f"\n\nn = {d['summary']['v0_naive']['overall']['n']} dev jobs with gold evidence; commit {d['provenance']['git_sha']}; embedder {d['provenance']['embedder']}.\n"


def rag_by_type() -> str:
    d = load("rag_benchmark.json")
    if not d:
        return ""
    types = ["reqs_4plus", "reqs_lt4", "has_implied", "fit_partial", "injection"]
    out = ["| variant | " + " | ".join(types) + " |", "|---" * (len(types) + 1) + "|"]
    for v in ("v0_naive", "v1_decomposition", "v2_hybrid", "v3_rerank", "v9_skill_graph"):
        bt = d["summary"][v]["by_type"]
        out.append(f"| {v} | " + " | ".join(f(bt.get(t, {}).get("recall@5")) for t in types) + " |")
    return "Recall@5 by job type:\n\n" + "\n".join(out) + "\n"


def ablation_table() -> str:
    d = load("rag_ablation.json")
    if not d:
        return "_rag_ablation.json pending_\n"
    out = ["| V9 configuration | Recall@5 | MRR | nDCG@10 | R@5 implied-skill jobs | R@5 explicit-only jobs |", "|---|---|---|---|---|---|"]
    for k, s in d["summary"].items():
        out.append(f"| {k} | {f(s['recall@5'])} | {f(s['mrr'])} | {f(s['ndcg@10'])} | {f(s['recall@5_has_implied'])} | {f(s['recall@5_explicit_only'])} |")
    return "\n".join(out) + "\n"


def b5_table() -> str:
    """B5: V0 vs shipped variant end to end on the same jobs (gigbid_graph rows)."""
    rows = []
    rag = load("rag_benchmark.json")
    for name, file, variant in (("V0 naive", "rag_e2e_v0.json", "v0_naive"), ("V9 skill graph (shipped)", "multiagent_comparison.json", "v9_skill_graph")):
        d = load(file)
        s = (d or {}).get("summary", {}).get("gigbid_graph")
        o = rag["summary"][variant]["overall"] if rag else {}
        rows.append(f"| {name} | {f(o.get('recall@5'))} | {f(o.get('ndcg@10'))} | {f(s.get('unsupported_claim_rate')) if s else 'pending'} | "
                    f"{f(s.get('judge_mean'), 2) if s else 'pending'} | {f(s.get('gigsim_reply_rate')) if s else 'pending'} | "
                    f"{f(s.get('p95_latency_s'), 1) if s else 'pending'} | {f(s.get('mean_cost_usd_proposal', s.get('mean_cost_usd')), 5) if s else 'pending'} |")
    return ("| variant | Evidence Recall@5 | nDCG@10 | unsupported claim rate (after verification) | judge score (1-10) | GigSim reply rate | p95 latency (s) | cost per job (USD) |\n"
            "|---|---|---|---|---|---|---|---|\n" + "\n".join(rows) + "\n")


def decision_table() -> str:
    out = ["| run | n | bid F1 | accuracy | scam recall | false-scam rate | price in band | unsupported claims before -> after | p95 latency (s) | cost/job (USD) |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for label, file in (("first matcher, default thresholds", "decision_eval_precalibration.json"), ("shipped (calibrated)", "decision_eval.json"),
                        ("hidden test", "hidden_test.json")):
        d = load(file)
        s = (d or {}).get("summary")
        if not s:
            out.append(f"| {label} | pending |||||||||")
            continue
        out.append(f"| {label} | {s['n']} | {f(s['bid_f1'])} | {f(s['accuracy'])} | {f(s['scam_recall'])} | {f(s['false_scam_rate'])} | {f(s['price_in_band'])} | "
                   f"{f(s['unsupported_claim_rate_before'])} -> {f(s['unsupported_claim_rate_after'])} | {f(s['p95_latency_s'], 1)} | {f(s['mean_cost_usd_job'], 5)} |")
    return "\n".join(out) + "\n"


def multiagent_table() -> str:
    d = load("multiagent_comparison.json")
    if not d:
        return "_multiagent_comparison.json pending_\n"
    out = ["| system | n | bid F1 | proposals | unsupported claim rate | judge (1-10) | GigSim reply rate | p95 latency (s) | mean tokens | cost/job (USD) | errors |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, s in d["summary"].items():
        out.append(f"| {k} | {s['n']} | {f(s['bid_f1'])} | {s['proposals']} | {f(s['unsupported_claim_rate'])} | {f(s['judge_mean'], 2)} | {f(s['gigsim_reply_rate'])} | "
                   f"{f(s['p95_latency_s'], 1)} | {f(s['mean_tokens'], 0)} | {f(s['mean_cost_usd'], 5)} | {s['errors']} |")
    return "\n".join(out) + "\n"


def tool_table() -> str:
    d = load("tool_granularity.json")
    if not d:
        return "_tool_granularity.json pending_\n"
    out = ["| design | tasks | success | tool-selection accuracy | argument accuracy | mean calls | mean tokens | p95 latency (s) | errors |", "|---|---|---|---|---|---|---|---|---|"]
    for k, s in d["summary"].items():
        out.append(f"| {k} | {s['tasks']} | {f(s['success_rate'])} | {f(s.get('tool_selection_accuracy'))} | {f(s.get('argument_accuracy'))} | {f(s['mean_calls'], 2)} | "
                   f"{f(s['mean_tokens'], 0)} | {f(s['p95_latency_s'], 1)} | {s['errors']} |")
    return "\n".join(out) + f"\n\nmodel: {d['provenance'].get('provider', 'groq')} {d['provenance']['model']}\n"


def injection_table() -> str:
    d = load("injection_eval.json")
    if not d:
        return "_injection_eval.json pending_\n"
    return "```json\n" + json.dumps(d["summary"], indent=1)[:1500] + "\n```\n"


SECTIONS = [("Retrieval (B2)", rag_table), ("Retrieval by job type", rag_by_type), ("Ablation of V9 (B4)", ablation_table),
            ("B5 results table", b5_table), ("Decisions end to end", decision_table), ("Multi-agent comparison (C)", multiagent_table),
            ("Tool granularity (A)", tool_table), ("Prompt injection (E4)", injection_table)]

if __name__ == "__main__":
    if "--json" in sys.argv:
        print(json.dumps({t: fn() for t, fn in SECTIONS}))
    else:
        for t, fn in SECTIONS:
            print(f"### {t}\n\n{fn()}")
