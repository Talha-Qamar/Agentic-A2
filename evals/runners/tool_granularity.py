"""R&D question A: Portfolio MCP tool granularity on 40 portfolio tasks with known correct calls.

Designs: coarse (one tool: match_requirements), bytype (many fine-grained tools: one search per document type),
rewritten (the default four-tool set with descriptions rewritten after reading the first two designs' failures),
and fine (the default set minus match_requirements, original descriptions).
Metrics per design: task success, tool-selection accuracy (first call is a correct tool for the task),
argument accuracy (a correct call carries the key term / id / outcome filter), tokens per task, latency.

    python -m evals.runners.tool_granularity --tasks 40

Each design is a separate Portfolio MCP server process (PORTFOLIO_TOOLSET=coarse|fine|bytype). A small model in a ReAct
loop solves each task using only that server's tools. Metrics: task success (auto-checked against the persona
ground truth), tool-call count, latency, wrong-tool rate (calls outside the expected tool family for the task type).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import re
import subprocess
import sys
import time

import httpx

from evals.runners.common import DATASETS, RowCache, mean, pct, provenance, quota_exhausted, write_result

PORTS = {"coarse": 8211, "fine": 8212, "bytype": 8213, "rewritten": 8214}
EXPECTED = {
    "coarse": {"evidence": {"match_requirements"}, "result": {"match_requirements"}, "skill": {"match_requirements"}, "outcome": {"match_requirements"}},
    "fine": {"evidence": {"search_evidence"}, "result": {"get_case_study", "search_evidence"}, "skill": {"list_skills", "search_evidence"},
             "outcome": {"search_evidence"}},
    "bytype": {"evidence": {"search_case_studies", "search_repositories", "search_reviews_and_cv"},
               "result": {"get_case_study", "search_case_studies", "search_reviews_and_cv"}, "skill": {"list_skills", "search_repositories", "search_case_studies"},
               "outcome": {"search_past_proposals"}},
    "rewritten": {"evidence": {"search_evidence"}, "result": {"get_case_study", "search_evidence"}, "skill": {"list_skills", "search_evidence"},
                  "outcome": {"search_evidence"}},
}


def args_ok(task: dict, name: str, args: dict) -> bool:
    """Argument accuracy: the call carries what the task needs (the key term, the right id, the outcome filter)."""
    blob = json.dumps(args).lower()
    term = str(task.get("term", "")).lower()
    if task["type"] == "outcome":
        if name == "search_past_proposals":
            return args.get("outcome") in ("won", "replied") or "won" in blob
        if name == "search_evidence":
            f = args.get("filters") or {}
            return "proposal" in (f.get("types") or []) and bool(set(f.get("outcomes") or []) & {"won", "replied"})
        return False
    if name == "list_skills":
        return task["type"] == "skill"
    if name == "get_case_study":
        return str(args.get("id", "")).lower() in {str(x).lower() for x in task.get("ids", [])}
    return bool(term) and term in blob


def make_tasks(n: int) -> list[dict]:
    rng = random.Random(40)
    tasks = []
    personas = ["ai_ml_engineer", "fullstack_web_dev", "data_analyst"]
    for persona in personas:
        man = json.loads((DATASETS / "gold" / f"{persona}_corpus_manifest.json").read_text())
        projects = man["projects"]
        props = [json.loads(line) for line in open(DATASETS.parent.parent / "data" / "personas" / persona / "past_proposals.jsonl")]
        for p in rng.sample(projects, 6):
            tag = rng.choice(p["tags"])
            clients = sorted({q["client"] for q in projects if tag in q["tags"]})
            tasks.append({"persona": persona, "type": "evidence", "q": f"A client needs {tag}. Which of my past clients did I do {tag} work for? Name the client.",
                          "check": {"any_of": clients}, "term": tag})
        for p in rng.sample(projects, 3):
            nums = re.findall(r"\d+(?:\.\d+)?", p["outcomes"][0])
            tasks.append({"persona": persona, "type": "result", "q": f"What measurable result did I achieve for {p['client']}? Quote the figure.",
                          "check": {"any_of": nums}, "term": p["client"], "ids": [p["id"]]})
        present = rng.choice(projects)["stack"][0]
        absent = rng.choice(["Unity", "Solidity", "SAP ABAP", "COBOL"])
        tasks.append({"persona": persona, "type": "skill", "q": f"Do I have portfolio evidence of using {present}? Answer yes or no.", "check": {"yes": True}, "term": present})
        tasks.append({"persona": persona, "type": "skill", "q": f"Do I have portfolio evidence of using {absent}? Answer yes or no.", "check": {"yes": False}, "term": absent})
        won = [x for x in props if x["outcome"] in ("won", "replied")]
        cat = rng.choice(won)["job_category"]
        tasks.append({"persona": persona, "type": "outcome",
                      "q": f"Give the id of one of my past proposals for {cat} work that got a reply or was won.",
                      "check": {"any_of": [x["proposal_id"] for x in won if x["job_category"] == cat]}})
        tasks.append({"persona": persona, "type": "outcome",
                      "q": "Give the id of one past proposal of mine that was won.", "check": {"any_of": [x["proposal_id"] for x in props if x["outcome"] == "won"]}})
    rng.shuffle(tasks)
    return tasks[:n]


def success(task: dict, answer: str) -> bool:
    a = (answer or "").lower()
    c = task["check"]
    if "any_of" in c:
        return any(str(x).lower() in a for x in c["any_of"])
    yes = bool(re.search(r"\byes\b", a)) and not re.search(r"\bno\b[,.]", a[:20])
    return yes == c["yes"]


async def run_design(design: str, tasks: list[dict], model, cache=None, tag: str = "", start: int = 0) -> list[dict]:
    from langchain_core.callbacks import UsageMetadataCallbackHandler
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langgraph.prebuilt import create_react_agent

    from common.tokens import mint_mcp_token
    rows = []
    for i, t in enumerate(tasks):
        key = f"{tag}{design}:{start + i}"
        if cache and cache.get(key):
            rows.append(cache.get(key))
            continue
        tok = mint_mcp_token("tool-study", t["persona"], None)
        client = MultiServerMCPClient({"p": {"transport": "streamable_http", "url": f"http://localhost:{PORTS[design]}/mcp",
                                             "headers": {"Authorization": f"Bearer {tok}"}}})
        tools = await client.get_tools()
        agent = create_react_agent(model, tools, prompt="You answer questions about the user's freelance portfolio using the tools. "
                                                         "Be brief; answer in one or two sentences.")
        cb = UsageMetadataCallbackHandler()
        t0 = time.perf_counter()
        try:
            out = await agent.ainvoke({"messages": [("user", t["q"])]}, {"callbacks": [cb], "recursion_limit": 14})
            msgs = out["messages"]
            answer = msgs[-1].content if isinstance(msgs[-1].content, str) else str(msgs[-1].content)
            tcs = [tc for m in msgs for tc in (getattr(m, "tool_calls", None) or [])]
            calls = [tc["name"] for tc in tcs]
            call_args = [tc.get("args") or {} for tc in tcs]
            err = None
        except Exception as e:  # noqa: BLE001
            answer, calls, call_args, err = "", [], [], f"{type(e).__name__}: {str(e)[:160]}"
        lat = time.perf_counter() - t0
        exp = EXPECTED[design][t["type"]]
        wrong = sum(c not in exp for c in calls)
        tokens = sum(u.get("input_tokens", 0) + u.get("output_tokens", 0) for u in cb.usage_metadata.values())
        right = [i for i, c in enumerate(calls) if c in exp]
        rows.append({"design": design, "persona": t["persona"], "type": t["type"], "q": t["q"], "answer": answer[:400], "success": success(t, answer) and not err,
                     "calls": calls, "args": call_args, "n_calls": len(calls), "wrong_tool_calls": wrong, "latency_s": round(lat, 2), "tokens": tokens, "error": err,
                     "tool_selected_ok": bool(calls) and calls[0] in exp,
                     "args_ok": any(args_ok(t, calls[i], call_args[i]) for i in right) if right else False})
        if quota_exhausted(err):
            rows.pop()
            print(f"STOP: daily quota reached at {key}", flush=True)
            raise QuotaStop(key)
        if cache:
            cache.put(key, rows[-1])
        print(f"[{design}] {t['type']:8s} ok={rows[-1]['success']} calls={calls} {lat:.1f}s", flush=True)
    return rows


class QuotaStop(Exception):
    pass


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=40)
    ap.add_argument("--designs", default="coarse,bytype,rewritten")
    ap.add_argument("--provider", default=os.environ.get("TOOL_STUDY_PROVIDER", "groq"))
    ap.add_argument("--model", default=os.environ.get("TOOL_STUDY_MODEL", "qwen/qwen3.8-27b"))
    ap.add_argument("--out", default="tool_granularity.json")
    a = ap.parse_args()
    from langchain_openai import ChatOpenAI

    from agent import settings
    prov = settings.get(f"providers.{a.provider}")
    model = ChatOpenAI(model=a.model, base_url=prov["base_url"], api_key=os.environ[prov["api_key_env"]], temperature=0,
                       max_tokens=600, timeout=90, max_retries=6)
    tasks = make_tasks(a.tasks)
    procs = []
    try:
        for d in a.designs.split(","):
            procs.append(subprocess.Popen([sys.executable, "-m", "mcp_servers.portfolio.server", "--transport", "http", "--port", str(PORTS[d])],
                                          env={**os.environ, "PORTFOLIO_TOOLSET": d}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        for d in a.designs.split(","):
            for _ in range(120):
                try:
                    httpx.get(f"http://localhost:{PORTS[d]}/mcp", timeout=1)
                    break
                except Exception:  # noqa: BLE001
                    time.sleep(0.5)
        rows, stopped = [], None
        cache = RowCache(a.out.removesuffix(".json") + "_" + a.model.replace("/", "_"))
        # interleaved (task i on every design before task i+1) so a run cut short by a daily cap stays balanced
        try:
            for i, t in enumerate(tasks):
                for d in a.designs.split(","):
                    rows += asyncio.run(run_design(d, [t], model, cache, start=i))
        except QuotaStop as e:
            stopped = f"daily quota reached at {e}"
            done = {(r["design"], r["q"]) for r in rows}
            rows += [r for r in cache.rows.values() if (r["design"], r["q"]) not in done]
    finally:
        for p in procs:
            p.terminate()
    paired = None
    if stopped:  # compare designs on the same tasks only
        common = set.intersection(*[{r["q"] for r in rows if r["design"] == d} for d in a.designs.split(",")]) if rows else set()
        rows, paired = [r for r in rows if r["q"] in common], len(common)
    summary = {}
    for d in a.designs.split(","):
        rs = [r for r in rows if r["design"] == d]
        if not rs:
            continue
        calls = sum(r["n_calls"] for r in rs)
        ok = [r for r in rs if not r["error"]]
        summary[d] = {"tasks": len(rs), "success_rate": round(mean([1.0 if r["success"] else 0.0 for r in rs]), 4),
                      "tool_selection_accuracy": round(mean([1.0 if r["tool_selected_ok"] else 0.0 for r in ok]), 4) if ok else None,
                      "argument_accuracy": round(mean([1.0 if r["args_ok"] else 0.0 for r in ok if r["tool_selected_ok"]]), 4)
                      if any(r["tool_selected_ok"] for r in ok) else None,
                      "mean_calls": round(calls / len(rs), 2), "wrong_tool_rate": round(sum(r["wrong_tool_calls"] for r in rs) / calls, 4) if calls else 0.0,
                      "p50_latency_s": round(pct([r["latency_s"] for r in rs], 50), 2), "p95_latency_s": round(pct([r["latency_s"] for r in rs], 95), 2),
                      "mean_tokens": round(mean([r["tokens"] for r in rs]), 1), "errors": sum(bool(r["error"]) for r in rs),
                      "by_type": {t: round(mean([1.0 if r["success"] else 0.0 for r in rs if r["type"] == t]), 3) for t in sorted({r["type"] for r in rs})}}
    write_result(a.out, {"provenance": provenance({"model": a.model, "provider": a.provider, "tasks": len(tasks)}), "summary": summary, "rows": rows,
                         "complete": not stopped, "stopped": stopped, "paired_tasks": paired})
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
