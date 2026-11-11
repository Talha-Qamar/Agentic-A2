"""Bid graph (C1): one thread per job.

    intake --Send--> {analyst, risk, matcher}  (parallel fan-out, reducers merge)  --> decide
    decide --(bid)--> pricing --(worth Connects)--> writer -> verifier -> critic --(revise <=2)--> writer
                                                                       critic --> compliance --(allowed)--> preview -> approval
    approval --approve--> submit ;  --edit--> preview (after compliance) ;  --reject--> END
    any node --failure after retries/fallback--> dead_letter ;  budget exhausted --> needs_attention

Postgres checkpointer (C6): interrupted threads survive restarts; submit is idempotent so a replay never resubmits.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from agent.nodes.analyst import analyst, intake
from agent.nodes.approval import approval, dead_letter, needs_attention, preview, submit
from agent.nodes.compliance import compliance
from agent.nodes.critic import critic
from agent.nodes.decide import decide
from agent.nodes.matcher import matcher
from agent.nodes.pricing import pricing
from agent.nodes.risk import risk
from agent.nodes.verifier import verifier
from agent.nodes.writer import writer
from agent.state import BidState

STOP = ("dead_letter", "needs_attention")


def fan_out(state: dict):
    if state.get("status") in STOP:
        return END
    return [Send("analyst", state), Send("risk", state), Send("matcher", state)]


def ok_then(nxt: str):
    def route(state: dict):
        return END if state.get("status") in STOP else nxt
    route.__name__ = f"to_{nxt}"
    return route


def build_bid_graph(checkpointer=None, store=None):
    g = StateGraph(BidState)
    g.add_node("intake", intake)
    g.add_node("analyst", analyst)
    g.add_node("risk", risk)
    g.add_node("matcher", matcher)
    g.add_node("decide", decide, destinations=("pricing", "dead_letter", END))
    g.add_node("pricing", pricing, destinations=("writer", END))
    g.add_node("writer", writer)
    g.add_node("verifier", verifier)
    g.add_node("critic", critic, destinations=("writer", "compliance"))
    g.add_node("compliance", compliance, destinations=("preview", END))
    g.add_node("preview", preview)
    g.add_node("approval", approval, destinations=("submit", "preview", "writer", END))
    g.add_node("submit", submit)
    g.add_node("dead_letter", dead_letter)
    g.add_node("needs_attention", needs_attention)

    g.add_edge(START, "intake")
    g.add_conditional_edges("intake", fan_out, ["analyst", "risk", "matcher", END])
    for n in ("analyst", "risk", "matcher"):
        g.add_edge(n, "decide")
    g.add_conditional_edges("writer", ok_then("verifier"), ["verifier", END])
    g.add_conditional_edges("verifier", ok_then("critic"), ["critic", END])
    g.add_conditional_edges("preview", ok_then("approval"), ["approval", END])
    g.add_edge("submit", END)
    g.add_edge("dead_letter", END)
    g.add_edge("needs_attention", END)
    return g.compile(checkpointer=checkpointer, store=store)


def mermaid() -> str:
    return build_bid_graph().get_graph().draw_mermaid()
