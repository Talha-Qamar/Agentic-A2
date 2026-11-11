"""Node runtime: dependencies, budgets, timeouts, retries, fallbacks, dead-letter routing and tracing.

Every node is wrapped by @node(...).  The wrapper
* stops the thread with status `needs_attention` when the step or token budget is exhausted (C5);
* applies a per-node timeout and bounded retries; on final failure uses the node's fallback (degraded but safe)
  or routes to `dead_letter` (C7);
* meters tokens/cost of every LLM call made inside the node and appends a trace record (E3);
* emits node_start / node_end events for live streaming to the UI.
"""
from __future__ import annotations

import asyncio
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from agent import settings
from agent.tracing import metering, span, trace_id_var


@dataclass
class Deps:
    """Runtime objects passed via config['configurable']['deps'] (never checkpointed)."""
    user_id: str
    persona: str
    profile: dict
    tools: dict[str, Any] = field(default_factory=dict)
    emit: Callable[[str, str, dict], None] = lambda node, kind, payload: None
    settings_override: dict = field(default_factory=dict)
    defences: dict = field(default_factory=lambda: {"delimit": True, "detect": True, "verify": True})
    style_rules: list[str] = field(default_factory=list)
    outcome_insights: list[str] = field(default_factory=list)

    def tools_for(self, agent: str) -> dict[str, Any]:
        from agent.mcp_client import allowlisted
        return allowlisted(self.tools, agent)

    async def call(self, agent: str, tool: str, args: dict) -> Any:
        from agent.mcp_client import call_tool
        self.emit(agent, "tool_call", {"tool": tool, "args": {k: (v if len(str(v)) < 200 else str(v)[:200] + "...") for k, v in args.items()}})
        t0 = time.perf_counter()
        try:
            out = await call_tool(self.tools_for(agent), tool, args)
            self.emit(agent, "tool_result", {"tool": tool, "ok": True, "ms": int((time.perf_counter() - t0) * 1000),
                                             "summary": _summ(out)})
            return out
        except Exception as e:
            self.emit(agent, "tool_result", {"tool": tool, "ok": False, "error": str(e)[:300]})
            raise


def _summ(o: Any) -> str:
    s = str(o)
    return s[:300] + ("..." if len(s) > 300 else "")


def get_deps(config: dict) -> Deps:
    return config["configurable"]["deps"]


def budget_exceeded(state: dict) -> str | None:
    if state.get("steps", 0) >= settings.get("budgets.max_steps_per_thread", 40):
        return f"step budget ({settings.get('budgets.max_steps_per_thread')}) exhausted"
    if state.get("tokens", 0) >= settings.get("budgets.max_tokens_per_thread", 60000):
        return f"token budget ({settings.get('budgets.max_tokens_per_thread')}) exhausted"
    return None


def node(name: str, fallback: Callable[[dict, Deps, Exception], Awaitable[dict]] | None = None, retries: int | None = None):
    def deco(fn: Callable[[dict, Deps], Awaitable[Any]]):
        async def wrapped(state: dict, config: RunnableConfig):
            deps = get_deps(config)
            if state.get("trace_id"):
                trace_id_var.set(state["trace_id"])
            over = budget_exceeded(state)
            if over:
                deps.emit(name, "budget_exceeded", {"reason": over})
                return Command(goto="needs_attention", update={"status": "needs_attention", "status_reason": f"{over} before {name}",
                                                               "trace": [{"node": name, "event": "budget_exceeded", "reason": over}]})
            deps.emit(name, "node_start", {})
            t0 = time.perf_counter()
            n_retry = settings.get("budgets.node_retries", 2) if retries is None else retries
            timeout = settings.get("budgets.node_timeout_s", 120)
            err: Exception | None = None
            out: Any = None
            degraded = False
            with metering() as m, span(f"node.{name}", {"gigbid.node": name}):
                for attempt in range(n_retry + 1):
                    try:
                        out = await asyncio.wait_for(fn(state, deps), timeout=timeout)
                        err = None
                        break
                    except Exception as e:  # noqa: BLE001
                        err = e
                        deps.emit(name, "node_retry", {"attempt": attempt + 1, "error": f"{type(e).__name__}: {str(e)[:200]}"})
                        await asyncio.sleep(min(4, 0.5 * 2 ** attempt))
                if err is not None and fallback is not None:
                    try:
                        out = await fallback(state, deps, err)
                        degraded = True
                        err = None
                    except Exception as e2:  # noqa: BLE001
                        err = e2
            rec = {"node": name, "ms": int((time.perf_counter() - t0) * 1000), "tokens": m.tokens, "cost_usd": m.cost,
                   "llm_calls": m.dump(), "degraded": degraded}
            if err is not None:
                rec["error"] = f"{type(err).__name__}: {str(err)[:400]}"
                deps.emit(name, "node_error", {"error": rec["error"], "trace": traceback.format_exception_only(type(err), err)[-1][:300]})
                return Command(goto="dead_letter", update={"status": "dead_letter", "status_reason": f"{name} failed: {rec['error']}",
                                                           "errors": [{"node": name, "error": rec["error"]}], "trace": [rec],
                                                           "steps": 1, "tokens": m.tokens, "cost_usd": m.cost})
            meta = {"steps": 1, "tokens": m.tokens, "cost_usd": m.cost, "trace": [rec]}
            if isinstance(out, Command):
                upd = dict(out.update or {})
                for k, v in meta.items():
                    upd[k] = (upd.get(k) or ([] if k == "trace" else 0)) + v if k != "trace" else (upd.get("trace") or []) + v
                deps.emit(name, "node_end", {"ms": rec["ms"], "tokens": m.tokens, "cost_usd": m.cost, "goto": str(out.goto)})
                return Command(goto=out.goto, update=upd, resume=out.resume)
            out = dict(out or {})
            for k, v in meta.items():
                out[k] = (out.get(k) or []) + v if k == "trace" else (out.get(k) or 0) + v
            deps.emit(name, "node_end", {"ms": rec["ms"], "tokens": m.tokens, "cost_usd": m.cost, "degraded": degraded,
                                         "keys": [k for k in out if k not in ("trace", "steps", "tokens", "cost_usd")]})
            return out
        wrapped.__name__ = name
        return wrapped
    return deco
