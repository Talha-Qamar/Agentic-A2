<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# triage-agent

An agent that classifies intent, pulls account context through the Zendesk API and drafts a reply for a human to approve, with long-running enrichment pushed to a worker queue.

**Stack:** Python, LangChain, Zendesk API, Postgres

## Why
Built for a saas client where first-response times above 9 hours because every ticket was triaged by hand.

## Quick start
```bash
pip install -r requirements.txt && python -m triage_agent.core data/sample.jsonl
```

## Results in production
- median first response dropped from 9.2 h to 47 min
- 63% of drafted replies sent with no edits

## Layout
- `src/` application code
- `tests/` unit tests
