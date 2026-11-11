# AI usage

The assignment allows AI coding assistants. This file records which one was used, for what, and what it got wrong.

## Tool

Claude (Anthropic), used as a coding agent through the Claude app with access to this repository, a Linux build
container and my Mac for long experiment runs. Account steps (GitHub, Groq, Kaggle, Render) and all secrets were
done by me; the assistant never saw or typed a password or API key.

## Where it was used

| area | files | how |
|---|---|---|
| Synthetic data generators | `data/generator/*` | drafted with the assistant from my spec of the personas and failure modes; I reviewed the persona bank and the gold-label rules |
| GigSim | `gigsim/*` | drafted with the assistant; frozen with checksums once the experiments started |
| Agents and graphs | `agent/*` | architecture decided first (`docs/adr/0001`), code drafted with the assistant, every node exercised by tests |
| MCP servers | `mcp_servers/*` | drafted with the assistant; schema snapshot test pins the surface |
| RAG variants and evaluation | `rag/*`, `evals/*` | drafted with the assistant; all numbers come from runs on my machine, committed in `evals/results/` |
| Web app | `apps/web/*` | drafted with the assistant; Playwright tests |
| Docs and report | `docs/*`, `README.md` | first drafts by the assistant from the results files; edited by me |

Prompts the agents use at runtime are in `agent/prompts/` and are part of the system, not assistant transcripts.

## Things it got wrong that were caught

1. **Past proposals counted as proof of skill.** The first fit matcher graded requirements against any retrieved
   evidence, including old proposals. Proposals often repeat a job's wording ("shipped Flutter apps") without the
   freelancer having done it, and grading ignored skills that only appear in code. The first end-to-end run
   (`evals/results/decision_eval_precalibration.json`) showed bid recall of 2/12 and that exposed it. The fix
   (`agent/nodes/matcher.py`: proof types only, project-level skills from the skill graph, thresholds set on a tune
   split) is commit `d124b79`.
2. **A `.gitignore` rule for experiment queues (`runs/`) also hid the web app's run-trace page**
   (`apps/web/src/app/runs/[id]/page.tsx`), so a clean clone would not have built. It was caught when a new file
   did not show up in `git status`, and fixed in `b551146`.
3. **Demo control endpoints were reachable without login** on the public URL (anyone could take the simulated
   marketplace down). They now need a signed-in user (`2c2df61`).
4. Smaller: LangGraph did not inject `config` until the node signature was annotated `RunnableConfig`; the node
   wrapper swallowed `interrupt()` until it re-raised `GraphBubbleUp`. Both were found by the integration test.

## What I checked myself

<!-- Fill in personally before submitting: which files you read line by line, which design decisions were yours,
     and anything you changed after review. -->
