<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# ab-toolkit

A reusable notebook and SQL templates for power analysis, CUPED variance reduction and sequential testing guardrails.

**Stack:** Python, SQL, BigQuery, Jupyter

## Why
Built for a gaming client where game designers shipped changes on tests that had not reached significance.

## Quick start
```bash
pip install -r requirements.txt && python -m ab_toolkit.core data/sample.jsonl
```

## Results in production
- test duration cut by about 30% with CUPED
- two false-positive launches prevented in the first quarter

## Layout
- `src/` application code
- `tests/` unit tests
