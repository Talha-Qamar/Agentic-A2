<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# routemate-warehouse

Ingested operational sources into BigQuery, modelled them in dbt and rebuilt the key reports in Looker Studio.

**Stack:** BigQuery, dbt, Python, Looker Studio

## Why
Built for a logistics client where the company ran on 40 linked Google Sheets that broke weekly.

## Quick start
```bash
pip install -r requirements.txt && python -m routemate_warehouse.core data/sample.jsonl
```

## Results in production
- retired 40 spreadsheets
- report refresh from manual weekly to automatic hourly

## Layout
- `src/` application code
- `tests/` unit tests
