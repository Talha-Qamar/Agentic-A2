"""Conversation graph: one thread per client conversation.

    load_thread -> intent -> liaison (question: portfolio evidence | negotiation: floor guardrail |
    interview: free slots | scam: polite on-platform decline) -> reply_compliance (+ dry run) -> reply_approval (interrupt)
    -> send (+ tentative calendar hold for interviews)
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent.nodes.approval import dead_letter, needs_attention
from agent.nodes.liaison import intent, liaison, load_thread, reply_approval, reply_compliance, send
from agent.state import ConversationState


def _ok(nxt):
    def r(s):
        return END if s.get("status") in ("dead_letter", "needs_attention") else nxt
    r.__name__ = f"to_{nxt}"
    return r


def route_intent(s):
    return END if s.get("status") in ("dead_letter", "needs_attention", "no_client_message") else "liaison"


def build_conversation_graph(checkpointer=None, store=None):
    g = StateGraph(ConversationState)
    g.add_node("load_thread", load_thread)
    g.add_node("intent", intent)
    g.add_node("liaison", liaison)
    g.add_node("reply_compliance", reply_compliance, destinations=("reply_approval", END))
    g.add_node("reply_approval", reply_approval, destinations=("send", "reply_compliance", END))
    g.add_node("send", send)
    g.add_node("dead_letter", dead_letter)
    g.add_node("needs_attention", needs_attention)
    g.add_edge(START, "load_thread")
    g.add_conditional_edges("load_thread", _ok("intent"), ["intent", END])
    g.add_conditional_edges("intent", route_intent, ["liaison", END])
    g.add_conditional_edges("liaison", _ok("reply_compliance"), ["reply_compliance", END])
    g.add_edge("send", END)
    g.add_edge("dead_letter", END)
    g.add_edge("needs_attention", END)
    return g.compile(checkpointer=checkpointer, store=store)
