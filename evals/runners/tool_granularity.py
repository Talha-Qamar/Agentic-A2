"""A5: Portfolio MCP tool-granularity study - coarse vs fine vs by-type tool designs on 40 portfolio tasks.

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

from evals.runners.common import DATASETS, mean, pct, provenance, write_result

PORTS = {"coarse": 8211, "fine": 8212, "bytype": 8213}
EXPECTED = {
    "coarse": {"evidence": {"match_requirements"}, "result": {"match_requirements"}, "skill": {"match_requirements"}, "outcome": {"match_requirements"}},
    "fine": {"evidence": {"search_evidence"}, "result": {"get_case_study", "search_evidence"}, "skill": {"list_skills", "search_evidence"},
             "outcome": {"search_evidence"}},
    "bytype": {"evidence": {"search_case_studies", "search_repositories", "search_reviews_and_cv"},
               "result": {"get_case_study", "search_case_studies", "search_reviews_and_cv"}, "skill": {"list_skills", "search_repositories", "search_case_studies"},
               "outcome": {"search_past_proposals"}},
}


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
                          "check": {"any_of": clients}})
        for p in rng.sample(projects, 3):
            nums = re.findall(r"\d+(?:\.\d+)?", p["outcomes"][0])
            tasks.append({"persona": persona, "type": "result", "q": f"What measurable result did I achieve for {p['client']}? Quote the figure.",
                          "check": {"any_of": nums}})
        present = rng.choice(projects)["stack"][0]
        absent = rng.choice(["Unity", "Solidity", "SAP ABAP", "COBOL"])
        tasks.append({"persona": persona, "type": "skill", "q": f"Do I have portfolio evidence of using {present}? Answer yes or no.", "check": {"yes": True}})
        tasks.append({"persona": persona, "type": "skill", "q": f"Do I have portfolio evidence of using {absent}? Answer yes or no.", "check": {"yes": False}})
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


async def run_design(design: str, tasks: list[dict], model) -> list[dict]:
    from langchain_core.callbacks import UsageMetadataCallbackHandler
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langgraph.prebuilt import create_react_agent

    from common.tokens import mint_mcp_token
    rows = []
    for t in tasks:
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
            calls = [tc["name"] for m in msgs for tc in (getattr(m, "tool_calls", None) or [])]
            err = None
        except Exception as e:  # noqa: BLE001
            answer, calls, err = "", [], f"{type(e).__name__}: {str(e)[:160]}"
        lat = time.perf_counter() - t0
        exp = EXPECTED[design][t["type"]]
        wrong = sum(c not in exp for c in calls)
        tokens = sum(u.get("input_tokens", 0) + u.get("output_tokens", 0) for u in cb.usage_metadata.values())
        rows.append({"design": design, "persona": t["persona"], "type": t["type"], "q": t["q"], "answer": answer[:400], "success": success(t, answer) and not err,
                     "calls": calls, "n_calls": len(calls), "wrong_tool_calls": wrong, "latency_s": round(lat, 2), "tokens": tokens, "error": err})
        print(f"[{design}] {t['type']:8s} ok={rows[-1]['success']} calls={calls} {lat:.1f}s", flush=True)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=int, default=40)
    ap.add_argument("--designs", default="coarse,fine,bytype")
    ap.add_argument("--model", default=os.environ.get("TOOL_STUDY_MODEL", "qwen/qwen3.8-27b"))
    ap.add_argument("--out", default="tool_granularity.json")
    a = ap.parse_args()
    from langchain_openai import ChatOpenAI
    model = ChatOpenAI(model=a.model, base_url="https://api.groq.com/openai/v1", api_key=os.environ["GROQ_API_KEY"], temperature=0,
                       max_tokens=600, timeout=60, max_retries=4)
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
        rows = []
        for d in a.designs.split(","):
            rows += asyncio.run(run_design(d, tasks, model))
    finally:
        for p in procs:
            p.terminate()
    summary = {}
    for d in a.designs.split(","):
        rs = [r for r in rows if r["design"] == d]
        calls = sum(r["n_calls"] for r in rs)
        summary[d] = {"tasks": len(rs), "success_rate": round(mean([1.0 if r["success"] else 0.0 for r in rs]), 4),
                      "mean_calls": round(calls / len(rs), 2), "wrong_tool_rate": round(sum(r["wrong_tool_calls"] for r in rs) / calls, 4) if calls else 0.0,
                      "p50_latency_s": round(pct([r["latency_s"] for r in rs], 50), 2), "p95_latency_s": round(pct([r["latency_s"] for r in rs], 95), 2),
                      "mean_tokens": round(mean([r["tokens"] for r in rs]), 1), "errors": sum(bool(r["error"]) for r in rs),
                      "by_type": {t: round(mean([1.0 if r["success"] else 0.0 for r in rs if r["type"] == t]), 3) for t in sorted({r["type"] for r in rs})}}
    write_result(a.out, {"provenance": provenance({"model": a.model, "tasks": len(tasks)}), "summary": summary, "rows": rows})
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
