<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# bnpl-fraud

A gradient-boosted classifier on application and device features with SHAP reason codes for analysts and monthly drift monitoring.

**Stack:** Python, XGBoost, SHAP, MLflow, Postgres

## Why
Built for a fintech client where rule-based fraud checks blocked good customers and missed coordinated fraud rings.

## Quick start
```bash
pip install -r requirements.txt && python -m bnpl_fraud.core data/sample.jsonl
```

## Results in production
- fraud losses down 38% at the same approval rate
- precision at 1% alert rate improved from 0.21 to 0.46

## Layout
- `src/` application code
- `tests/` unit tests
