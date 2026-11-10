<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# elasticity-study

Estimated price elasticity by category with controls for promotions and seasonality and simulated margin impact.

**Stack:** Python, statsmodels, SQL, Tableau

## Why
Built for a e-commerce client where discounts were set by intuition and margins were shrinking.

## Quick start
```bash
pip install -r requirements.txt && python -m elasticity_study.core data/sample.jsonl
```

## Results in production
- recommended price changes lifted gross margin 1.8 points in the test categories
- discount depth reduced on inelastic categories

## Layout
- `src/` application code
- `tests/` unit tests
