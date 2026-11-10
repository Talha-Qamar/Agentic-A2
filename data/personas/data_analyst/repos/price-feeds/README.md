<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# price-feeds

A daily pipeline that pulls partner product feeds through their official APIs, validates them and charts price moves.

**Stack:** Python, Airflow, Postgres, Metabase

## Why
Built for a e-commerce client where manual competitor price checks covered only 50 products.

## Quick start
```bash
pip install -r requirements.txt && python -m price_feeds.core data/sample.jsonl
```

## Results in production
- coverage from 50 to 8,000 products
- pricing decisions reviewed daily instead of monthly

## Layout
- `src/` application code
- `tests/` unit tests
