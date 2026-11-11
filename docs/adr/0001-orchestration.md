# ADR 0001: LangGraph graph with a deterministic decision node

**Context.** The workflow has parallel analysis, a bounded critique loop, a human approval pause that must survive
restarts, and strict budgets.
**Decision.** One LangGraph `StateGraph` per job thread (and one per client conversation) with a Postgres checkpointer,
`Send` fan-out for analyst/risk/matcher, `interrupt()` for approval, `Command` routing for dead-letter / needs-attention.
The bid/skip decision is a rule over evidence-based scores, not an LLM call.
**Alternatives.** A single ReAct agent with all tools; a supervisor (langgraph-supervisor) team. Both were built and
measured (`evals/results/multiagent_comparison.json`).
**Consequences.** Every step is explainable and individually traceable; the decision cannot be argued into BID by
injected text; more code than a ReAct agent.
