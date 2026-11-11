<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# agent-redteam

Untrusted-content delimiting, tool permission tiers, a red-team suite of 150 attacks and PII masking in logs.

**Stack:** Python, LangGraph, Guardrails, pytest

## Why
Built for a travel client where a booking agent could be talked into issuing refunds by instructions hidden in emails.

## Quick start
```bash
pip install -r requirements.txt && python -m agent_redteam.core data/sample.jsonl
```

## Results in production
- attack success rate fell from 34% to 3% on the red-team suite
- no PII in traces after the rollout audit

## Layout
- `src/` application code
- `tests/` unit tests
