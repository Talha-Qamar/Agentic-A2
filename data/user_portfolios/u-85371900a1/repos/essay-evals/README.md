<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# essay-evals

A golden set of 400 graded essays, an LLM judge calibrated against teacher labels and a CI gate on every prompt change.

**Stack:** Python, pytest, LangSmith, GPT-4-class models

## Why
Built for a edtech client where prompt changes shipped weekly with no way to tell whether feedback quality got worse.

## Quick start
```bash
pip install -r requirements.txt && python -m essay_evals.core data/sample.jsonl
```

## Results in production
- judge agreement with teachers of Cohen's kappa 0.71
- caught two regressions before release in the first month

## Layout
- `src/` application code
- `tests/` unit tests
