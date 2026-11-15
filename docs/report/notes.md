## budgets
Latency budgets are missed and cost budgets are met. The p95 latency is several times the 25 s declared; the trace
timings show where it goes: on Groq's free tier each model is limited to 8,000 tokens per minute, so a proposal
(about 12K tokens across writer, verifier, critic and compliance) waits for the per-minute window to reopen, and the
three parallel analysis branches queue behind each other. Model compute itself is a few seconds per node. The
declared budget assumed an unthrottled endpoint; on this tier the honest numbers are the ones in the table. What
would meet it: a paid tier (no per-minute cap), or the local profile for the analysis branches. Cost stays under
budget because a skipped job stops before any strong-model call.

## multiagent
Two of the three designs could not run reliably on the free tier, and why is the finding. The single ReAct agent
holds all twenty tools, so every request carries every tool schema plus the growing transcript; five of six jobs
failed with HTTP 413 (one request above Groq's 8K-token per-request cap) and the sixth called a tool that does not
exist (HTTP 400). Trimming tool results to 1,200 characters did not save it: the schemas alone are most of the budget.
The supervisor splits tools across two specialists and fits, but three of six jobs ended on the same 400 (the
supervisor invented a tool name). The hand-built graph finished every job; one draft could not be saved to GigSim
(an authorisation error in the preview step). Its proposals drew a simulated client reply 3 times out of 3,
against 2 of 3 for the supervisor. The LLM judge scored the supervisor's letters higher (9.0 against 5.7) even
though the independent claim check found more unsupported claims in them (0.83 against 0.50): the judge rewards
fluent, confident letters, which is why GigBid does not use it to decide anything and why it is calibrated against
human labels before its scores are reported. Six jobs per system is a small sample; the failure modes, not the
means, are the result. **What ships:** the hand-built graph, because only it finished every job and its tool
surface per step stays small enough for a capped endpoint.
