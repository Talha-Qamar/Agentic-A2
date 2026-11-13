## budgets
Latency budgets are missed and cost budgets are met. The p95 latency is several times the 25 s declared; the trace
timings show where it goes: on Groq's free tier each model is limited to 8,000 tokens per minute, so a proposal
(about 12K tokens across writer, verifier, critic and compliance) waits for the per-minute window to reopen, and the
three parallel analysis branches queue behind each other. Model compute itself is a few seconds per node. The
declared budget assumed an unthrottled endpoint; on this tier the honest numbers are the ones in the table. What
would meet it: a paid tier (no per-minute cap), or the local profile for the analysis branches. Cost stays under
budget because a skipped job stops before any strong-model call.
