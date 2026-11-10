<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# ga4-attribution

GA4 raw-event export to BigQuery, a data-driven attribution model and a campaign ROI dashboard.

**Stack:** GA4, BigQuery, SQL, Looker Studio

## Why
Built for a retail client where the marketing team credited every sale to the last click.

## Quick start
```bash
pip install -r requirements.txt && python -m ga4_attribution.core data/sample.jsonl
```

## Results in production
- shifted 20% of spend from branded search to prospecting
- blended ROAS up 14% over the next two months

## Layout
- `src/` application code
- `tests/` unit tests
