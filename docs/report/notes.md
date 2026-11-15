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
fluent, confident letters, which is why GigBid does not use it to decide anything and why its scores here are
indicative until it is checked against human labels. Six jobs per system is a small sample; the failure modes, not the
means, are the result. **What ships:** the hand-built graph, because only it finished every job and its tool
surface per step stays small enough for a capped endpoint.

## tools
The hypothesis is not supported on this sample. The six fine-grained by-type tools had the highest task success
(9 of 13), the single coarse tool the lowest (4 of 13), and the rewritten descriptions sat in between (6 of 12) at
twice the tokens and latency. The dominant failure was the same in every design: the model called a tool without a
required argument (for example `match_requirements` with no `job_text`), and Groq rejected the call against the
schema before it reached the server (HTTP 400; 5, 4 and 4 tasks). A coarse tool with one long free-text parameter
was the easiest to call wrongly, and twice the model answered without calling it at all. The rewritten set added two
loops that hit the recursion limit (get_case_study and search_evidence called in turn). Caveats: the run stopped at
the free tier's daily cap after 13 of 40 tasks (11 paired across all three designs), one small model, two errors
were infrastructure (a dropped connection). **What we kept:** the default four task-shaped tools. The next change, not yet measured, is
to name the required arguments in the first line of each description and to expose the typed by-type search tools
alongside them.

## injection
Two layers are deterministic and were measured on 30 paraphrased attacks written after the patterns were frozen.
The pattern screen is overfit to the attack templates it was written against: it flagged 8 of 30 paraphrases
(27%), caught role-spoofed and hidden-comment attacks, and missed every polite, preference-style and obfuscated one,
with no false positive on 20 benign posts that share the vocabulary. The output guard is what holds: for the 20
attacks whose goal is text in the proposal (contact details, links, guarantees, prompt leakage), it stripped 17
payloads from an otherwise normal letter, and screen plus guard together caught 18. The two misses were a guarantee
paraphrased as a pledge ("you won't pay a cent") and an obfuscated link ("fasthire [dot] io"). The other two goals
cannot succeed through text at all: the bid decision and the price come from deterministic code that does not read
the post's instructions. The end-to-end run through the full graph with the LLM layers on (wrapping, untrusted-data
note, LLM compliance) stopped at the daily token cap after one attack, so the end-to-end attack success rate is not
reported here. **What changed:** we did not tune the patterns on the red-team set (that would make it a training
set); the finding moves the weight of the defence onto the structural rules and the output guard.

## b5
With naive dense retrieval (V0) in the same graph, the agent skipped all six jobs, including the three it should
have bid on: the evidence V0 returns for each requirement is too weak for the matcher to grade it as supported, so
the fit score stayed under the threshold and no proposal was written. With V9 the same graph bid on three jobs
(two correct) and every submitted draft drew a simulated client reply; the independent claim check is discussed in §5.
Six jobs is a small sample; the result is that retrieval quality decides whether the agent bids at all, which the
offline Recall@5 gap (0.441 against 0.672) predicts. Where better retrieval did *not* show up is the simulated reply rate: every submitted V9
draft drew a reply, but so did two of three supervisor drafts whose claims were mostly unsupported (§5). GigSim's
reply model (`gigsim/engine.py`) scores whether the letter names the client's must-have skills, how many figures
it contains, the opening line and the price; it cannot tell a proven figure from an invented one, so an unsupported
"cut latency by 60%" earns the same specificity credit as a cited one. At this sample size retrieval quality
changes whether the agent bids, not whether the simulated client replies.
