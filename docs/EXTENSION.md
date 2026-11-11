# Signature extension: X3 Portfolio builder

> Turn a GitHub account into case studies automatically, verified against the code, and feed them to the Portfolio
> server.

## Why this one

The retrieval experiments kept failing in the same place: requirements whose only evidence was code. The personas
were built that way on purpose (three projects per persona have a repository but no case study, two have a
README that says almost nothing), and real freelancers look the same - the work is on GitHub, the write-up never
happened. A better retriever cannot find a sentence nobody wrote. X3 attacks the cause instead of the symptom.

## What it does

```
GitHub repo ──(GitHub MCP: get_file_contents)──> README + code
      │
      ├─ draft    agent/prompts/case_study_builder.md  (LLM, repo text only; deterministic draft without a model)
      ├─ verify   every claim checked against THIS repo's chunks:
      │             BM25 candidates -> cross-encoder support + number/entity checks (rag/verify.py)
      │             + code check: a claim naming libraries is supported only if each one occurs in a code file
      ├─ remove   unsupported sentences are deleted before anything is saved
      └─ save     user portfolio case_studies/builder-<repo>.md  (front matter records the verification)
                         │
                         └─> next search_evidence / match_requirements call re-indexes incrementally
                             (portfolio signature changed -> only new chunks are embedded)
```

Second half - what to write next (`agent/portfolio_builder.py`, Settings -> Portfolio builder):

1. **Gap mining** - requirements graded `none`/`partial` on jobs the freelancer had to skip or watch, grouped by
   skill and weighted by the budget they would have unlocked.
2. **Hidden strengths** - skills that occur in repository code or READMEs but in no case study, CV line or review.
3. **Ranking** - jobs affected x budget weight x 2 when hidden evidence exists. Suggestions with hidden evidence
   link straight to "Build and verify" for that repo.

Code: `agent/case_study_builder.py`, `agent/portfolio_builder.py`, `rag/ingest/github_mcp.py`,
`apps/api/routers/workspace.py` (`POST /api/portfolio/from-github`, `GET /api/portfolio/suggestions`),
`apps/web/src/app/settings/PortfolioBuilder.tsx`. Tests: `tests/unit/test_case_study_builder.py`,
`tests/unit/test_github_mcp_ingest.py`, `tests/unit/test_incremental_reindex.py`,
`apps/web/e2e/portfolio_builder.spec.ts`.

## How it was measured

`python -m evals.runners.portfolio_builder_eval` (no LLM, deployed retrieval and matcher):

* per persona, run the Fit Matcher on the first half of the dev set and take the builder's top suggestions;
* add the top-3 suggested write-ups, built only from each repo's own text (no new facts), to a copy of the portfolio;
* re-run on the **held-out second half** and compare requirement coverage, fit and bid decisions on the jobs that
  need the suggested skills.

Results: `evals/results/portfolio_builder_eval.json` (summary table in the report, section 7).

Claim verification of builder drafts is unit-tested with an invented claim ("cut cloud costs by 73% for a Fortune
500 bank using Kubernetes") that must be removed while a code-backed claim ("Celery, Redis and LangChain") is kept.

## Limits

* The persona repositories are synthetic and small; the code check is lexical (a library name in an import or
  requirements file), so it proves *use*, not depth.
* Results ("cut latency by 40%") can only come from the README; if the README states none, the case study says so.
* On the deployed instance the GitHub MCP server needs `npx`; if it cannot start, the endpoint falls back to the
  repository checkout for this project's own sample repos and labels the source accordingly. Other repos then fail
  with a clear error instead of silently using a different path.
