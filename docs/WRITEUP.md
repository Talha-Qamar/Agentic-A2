# Relevant is not the same as proven: what a freelancer copilot taught me about retrieval

*Talha Qamar · AI-4016 Agentic AI, FAST-NUCES · code and every number: github.com/Talha-Qamar/Agentic-A2*

For a course project I built GigBid: a set of agents that reads a freelancer's job feed, decides which jobs are worth
a bid, and drafts proposals that a human approves before anything is sent. The whole system rests on one question
asked over and over: *for this requirement in this job post, what in the freelancer's own portfolio proves they can
do it?* If the answer is weak, the right move is to skip the job. If it is strong, the proposal should cite it.

I expected the hard part to be the agents: the graph, the hand-offs, the approval step. It wasn't. The most
surprising result of the project was that the components I trusted to measure *relevance* kept failing at the job I
actually needed, which was finding *proof*. It happened three times, in three different parts of the system, and the
pattern was the same each time.

## The setup, briefly

There are three synthetic freelancers (an ML engineer, a full-stack developer and a data analyst). Each has a CV, case
studies in different writing styles, 14–15 code repositories, client reviews and about 150 past proposals. For 600
labelled job posts I know which portfolio items really prove each requirement. That gives a retrieval benchmark
(247 jobs with gold evidence) and a decision benchmark (should the agent bid or skip?).

I implemented nine retrieval variants, from naive dense search to a skill graph, and measured Recall@5: how often a
gold project shows up in the top five results for a requirement.

## Surprise 1: the reranker made things worse

Everyone's standard advice for RAG is to retrieve broadly and then rerank with a cross-encoder. Cross-encoders read
the query and the passage together, so they should be strictly better judges of relevance than a bi-encoder. I added
one (ms-marco-MiniLM-L-6) on top of my hybrid BM25 + dense retriever.

Recall@5 went **down**, from 0.574 to 0.514. A different, much smaller embedding model (WordLlama) gave the same
ordering, 0.606 to 0.526, so it was not one model's quirk. Adding the reranker to my best variant also cost recall
(0.676 to 0.660 in the ablation).

When I looked at what the reranker promoted, the reason was obvious in hindsight. Over the top five results for 1,245 requirement slots, the reranker raised the share of past proposals from 73% to 79% and halved the share of code (11% to 6%), while the share of results that belonged to a gold project fell from 50% to 46%. A past
proposal that says "I have built RAG pipelines with LangChain" is an almost perfect paraphrase of the requirement
"experience building RAG pipelines with LangChain". A repository file that imports `langchain`, builds a retriever
and evaluates it is not a paraphrase of anything. It reads like code. The cross-encoder was trained to judge whether
a passage *answers a search query*, and by that standard the sales pitch wins. But the sales pitch proves nothing; it
is the freelancer's own claim, repeated.

So the reranker was doing its job perfectly well. It was just the wrong job.

## Surprise 2: my own matcher had the same bug

Before I understood the reranker result, I had already built the same mistake into the fit matcher. The matcher
grades each requirement as strongly, partially or not supported, based on the retrieved evidence. On the first full
decision run, the agent bid on almost nothing it should have: bid F1 was **0.29**, with every scam correctly skipped
but most good jobs skipped too.

Two causes, both the same idea. First, past proposals counted as evidence. A proposal that mentioned a tool made that tool
look supported, which is circular: the agent was citing its own previous pitches as proof. Second, skills that
appear only in code were not credited at all, because the evidence item exposed only the skills of the text chunk,
not of the project it came from. A repository whose code actually uses Celery counted for less than a
proposal that once mentioned Celery.

After the fix, proposals can no longer prove a skill, and an evidence chunk carries the skills of its whole project
(code included). Combined with the next change, bid F1 went from 0.29 to **0.87** on the same 21 jobs.

## Surprise 3: the threshold everyone would pick was wrong

The bid rule is deterministic on purpose: the LLM never decides "bid" by itself, so a job post cannot talk its way
into a bid. It compares a fit score to a threshold. I had set that threshold to 0.55 by hand, which feels like a
sensible "more than half of the requirements are covered" line.

On 272 held-out jobs, 0.55 gave precision 1.0 but recall 0.28, so F1 was **0.43**. The agent was extremely sure
whenever it bid, and it almost never bid. The median fit score of jobs that *should* get a bid was 0.475. When I
chose the threshold on a separate tune split instead, it landed at 0.175, and F1 on the held-out split was
**0.81**.

Why so low? Because a fit score built from *proof* is naturally much lower than one built from *relevance*. Most job
posts list a few generic requirements ("good communication", "available in my time zone") that no portfolio item
proves, and many real requirements are only partly evidenced. A freelancer who can prove the three requirements that
matter is a good bid, even if the score looks like a failing grade. My intuition for the threshold came from
relevance scores, and it was wrong once the score measured something stricter.

## The common thread

All three failures were the same substitution: something that measures *how similar a text is to the requirement*
was used where I needed *whether the text is evidence for it*. Similarity favours self-description (proposals, CV
summary lines), which is exactly the material a careful reader would discount. Evidence is often written in a
different register entirely: code, a number in a case study, a client's review.

What worked was making evidence structural instead of semantic. The retriever I shipped (V9) maps each requirement to
canonical skills, finds projects that demonstrate those skills in any of their artefacts (code, README, case study,
review), boosts projects with good outcomes, and only falls back to hybrid search when a requirement names no known
skill. It reached Recall@5 **0.672** against 0.441 for naive dense retrieval, with no model call at query time
(p95 under 0.1 s). The ablation shows the parts that matter: removing the hybrid fallback or the requirement
decomposition costs the most on jobs whose requirements are implied rather than named.

The same idea runs through the claim verifier that checks every proposal before a human sees it. A sentence like
"I cut inference latency by 40%" is kept only if a cited piece of evidence supports it. That means cross-encoder
support plus an exact check that the number and any named tool appear in the evidence. In that setting, where I
compare a claim to *one* specific passage instead of ranking many, the cross-encoder works well: unsupported claims
fell from 25% to 0% of claims before the critic saw the draft.

## What I would tell someone building a similar system

I am wary of turning one course project into general advice, and the data is synthetic, generated by me, which
favours a skill-based retriever on requirements that name a skill. (Recall on jobs with implied requirements is
reported separately; V9 still leads there, by less.) With that caveat, here are three things I now check first:

* **Ask what your retriever is rewarded for.** If the corpus mixes claims about work with artefacts of work, a
  relevance model will prefer the claims. Measure the document types in your top results before adding a reranker.
* **Treat the system's own past outputs as a separate class.** Past proposals are useful as style examples and
  outcome signals. They are not evidence, and letting them count as evidence creates a loop.
* **Calibrate thresholds on held-out data, never by feel.** A score that measures something strict will sit lower
  than you expect. A threshold set by hand produced a system that looked careful (precision 1.0) and was useless
  (recall 0.28).

The agents, the approval gate and the MCP servers were the parts I expected to write about. The finding I didn't
expect was that "relevant" and "proven" come apart, and that standard RAG tools are built for the first.
