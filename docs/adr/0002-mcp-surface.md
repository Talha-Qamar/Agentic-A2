# ADR 0002: Three MCP servers; writes need idempotency, dry run and a human approval token

**Decision.** Portfolio (read-only), Marketplace (reads + draft/submit/send) and Workspace (calendar, email drafts)
servers built with the official MCP Python SDK (FastMCP, Streamable HTTP + stdio). Marketplace writes require an
idempotency key, support `dry_run` (default true for submits/sends) and, when not a dry run, an HMAC approval token
that only the API mints after a human approves. Bearer JWTs carry the user, persona and marketplace credential
reference; a per-user rate limiter sits below GigSim's limit; every call is written to an append-only audit log.
**Why.** Puts the safety property (no unapproved sends or spends) in the tool layer, so even a compromised or confused
agent cannot violate it. The marketplace server is one interface with two adapters (GigSim, Upwork live).
**Granularity.** Chosen from the tool-granularity study (`evals/results/tool_granularity.json`).
