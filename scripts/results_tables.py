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


def change_table() -> str:
    b, a = load("change_request_before.json"), load("change_request_after.json")
    if not (b and a):
        return "_change_request_*.json pending_\n"
    out = ["| policy pack | jobs | drafted | marketplace dry run accepts | rejects | disclosure line added | dead letter |", "|---|---|---|---|---|---|---|"]
    for label, d in (("before (70c8062 rules)", b), ("after (a783067 rules)", a)):
        s, rows = d["summary"], d["rows"]
        disc = sum(1 for r in rows if "Drafted with AI assistance" in (r.get("cover_letter") or ""))
        out.append(f"| {label} | {s['n']} | {s['proposals_drafted']} | {s.get('marketplace_would_accept', '-')} | {s.get('marketplace_would_reject', '-')} | "
                   f"{disc} | {s['dead_letter']} |")
    return "\n".join(out) + f"\n\nGigSim policy 2026-11-02 in both runs; commit {a['provenance']['git_sha']}; profile {a['provenance']['profile']}.\n"


def builder_table() -> str:
    d = load("portfolio_builder_eval.json")
    if not d:
        return "_portfolio_builder_eval.json pending_\n"
    out = ["| persona | case studies built | claims checked | unsupported removed | held-out jobs affected | coverage before -> after | fit before -> after | bids before -> after |",
           "|---|---|---|---|---|---|---|---|"]
    for p, r in d["summary"].items():
        cl = sum(b["verification"]["claims"] for b in r["built"])
        un = sum(b["verification"]["unsupported"] for b in r["built"])
        out.append(f"| {p} | {len(r['built'])} ({', '.join(b['repo'] for b in r['built'])}) | {cl} | {un} | {r['heldout_jobs_affected']} | "
                   f"{f(r['coverage_before'])} -> {f(r['coverage_after'])} | {f(r['fit_before'])} -> {f(r['fit_after'])} | {r['bids_before']} -> {r['bids_after']} |")
    llm = d.get("llm_case_studies")
    tail = ""
    if llm:
        tail = (f"\n\nLLM drafting check: {llm.get('claims')} claims written by the model, unsupported before verification "
                f"{f(llm.get('unsupported_rate_before_verification'))}, after {f(llm.get('unsupported_rate_after'))}.\n")
    return "\n".join(out) + tail + "\n"


def budgets_table() -> str:
    d = load("hidden_test.json") or load("decision_eval.json")
    if not d:
        return "_hidden_test.json pending_\n"
    src = "hidden_test.json" if load("hidden_test.json") else "decision_eval.json (hidden test pending)"
    s, b = d["summary"], d.get("declared_budgets") or {}
    rows = [("p95 latency per job analysed (s)", b.get("p95_latency_s_job_analysed"), s.get("p95_latency_s")),
            ("p95 latency per proposal (s)", b.get("p95_latency_s_proposal"), s.get("p95_latency_s_proposal")),
            ("cost per job analysed (USD)", b.get("usd_per_job_analysed"), s.get("mean_cost_usd_job")),
            ("cost per proposal (USD)", b.get("usd_per_proposal"), s.get("mean_cost_usd_proposal"))]
    out = ["| budget | declared | measured | met |", "|---|---|---|---|"]
    for name, dec, meas in rows:
        met = "-" if dec is None or meas is None else ("yes" if meas <= dec else "no")
        out.append(f"| {name} | {dec} | {f(meas, 4) if isinstance(meas, float) else f(meas)} | {met} |")
    q = [("bid F1", s.get("bid_f1")), ("scam recall", s.get("scam_recall")), ("price in band", s.get("price_in_band")),
         ("unsupported claims after verification", s.get("unsupported_claim_rate_after")), ("dead letter", s.get("dead_letter"))]
    return ("\n".join(out) + f"\n\nQuality on the same run ({src}, n={s['n']}, profile {d['provenance'].get('profile')}): "
            + ", ".join(f"{k} {f(v)}" for k, v in q) + ".\n")


FIX = {"wrong skip (fit too low)": ("Matcher counted past proposals as proof and ignored code-only skills; threshold 0.55 set by hand",
                                    "Proposals no longer prove skills, code-level skills count (d124b79); threshold calibrated on a tune split (12b71fc)", "yes: bid F1 0.29 -> 0.87"),
       "wrong bid": ("Partial-fit job scored at the bid threshold", "None yet: calibrated threshold trades this for recall", "open"),
       "mispriced (below band)": ("Fixed-price jobs whose client budget max (190-310 USD) is below the fair band (330-550 USD): pricing never quotes above the client's max",
                                   "Kept on purpose (quoting over budget lowers reply odds in GigSim); the rationale now states the gap", "no (design choice)"),
       "unsupported claim": ("Writer stated a figure or tool not in the cited evidence", "Verifier removes the sentence before the critic", "yes: 0 after verification"),
       "compliance false positive": ("LLM compliance flagged 'The hourly rate is $41' as off-platform payment", "Block needs a concrete marker in the span (agent/nodes/compliance.py)", "yes: unit test"),
       "tool error (LLM quota)": ("Groq free tier daily token cap hit mid-run (HTTP 429)", "Ordered fallback list, skip exhausted providers (b21c847); Cerebras profile", "partly: fallback also capped"),
       "needs attention": ("Marketplace dry run or budget stop", "Human sees the reason in the studio", "by design"),
       "injection present": ("Planted instruction in the post", "Screen + wrap + output guard", "see 9")}


def classify(r: dict) -> list[str]:
    c = []
    st = r.get("status")
    if st == "dead_letter" and "429" in json.dumps(r.get("errors") or r.get("error") or ""):
        c.append("tool error (LLM quota)")
    if st == "blocked" and r.get("compliance"):
        c.append("compliance false positive")
    if r["gold"] == "bid" and r["pred"] == "skip" and not r.get("gold_scam"):
        c.append("wrong skip (fit too low)")
    if r["gold"] == "skip" and r["pred"] == "bid":
        c.append("wrong bid")
    if r.get("price") is not None and r.get("band") and r["price"] < r["band"][0]:
        c.append("mispriced (below band)")
    if (r.get("unsupported_before") or 0) > 0:
        c.append("unsupported claim")
    if st == "needs_attention":
        c.append("needs attention")
    return c


def failures_table() -> str:
    cats: dict[str, list[str]] = {}
    for file in ("decision_eval_precalibration.json", "decision_eval.json"):
        d = load(file)
        for r in (d or {}).get("rows", []):
            for c in classify(r):
                cats.setdefault(c, []).append(f"{r['job_id'][4:10]}{'*' if 'precal' in file else ''}")
    if not cats:
        return "_decision runs pending_\n"
    out = ["| category | jobs (n) | cause found in the trace | fix tried | worked? |", "|---|---|---|---|---|"]
    for c, jobs in sorted(cats.items(), key=lambda x: -len(x[1])):
        cause, fix, ok = FIX.get(c, ("", "", ""))
        out.append(f"| {c} | {len(jobs)}: {', '.join(jobs[:8])}{' ...' if len(jobs) > 8 else ''} | {cause} | {fix} | {ok} |")
    n = len({j for js in cats.values() for j in js})
    return "\n".join(out) + f"\n\n{n} distinct failed job runs; * = run before the matcher fix and calibration. Taxonomy categories with no failure in these runs (generic opening) are not listed.\n"


SECTIONS = [("Retrieval (B2)", rag_table), ("Retrieval by job type", rag_by_type), ("Ablation of V9 (B4)", ablation_table),
            ("B5 results table", b5_table), ("Decisions end to end", decision_table), ("Multi-agent comparison (C)", multiagent_table),
            ("Tool granularity (A)", tool_table), ("Prompt injection (E4)", injection_table)]

README_KEYS = {"rag": rag_table, "b5": b5_table, "decisions": decision_table, "multiagent": multiagent_table,
               "tools": tool_table, "injection": injection_table}


def fill_readme(text: str) -> str:
    """Replace every <!-- table:KEY --> ... <!-- /table --> block with freshly generated markdown."""
    import re
    return re.sub(r"(<!-- table:(\w+) -->\n).*?(<!-- /table -->)", lambda m: m.group(1) + README_KEYS[m.group(2)]().strip() + "\n" + m.group(3),
                  text, flags=re.S)


if __name__ == "__main__":
    if "--readme" in sys.argv:
        rp = R.parents[1] / "README.md"
        rp.write_text(fill_readme(rp.read_text()))
        print("README tables regenerated")
    elif "--json" in sys.argv:
        print(json.dumps({t: fn() for t, fn in SECTIONS}))
    else:
        for t, fn in SECTIONS:
            print(f"### {t}\n\n{fn()}")
