<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# store-sites

Catchment analysis combining census density, competitor locations and existing store sales to score sites.

**Stack:** Python, GeoPandas, QGIS, SQL

## Why
Built for a retail client where new stores were opened on landlord recommendations.

## Quick start
```bash
pip install -r requirements.txt && python -m store_sites.core data/sample.jsonl
```

## Results in production
- ranked 120 candidate sites
- first two recommended stores beat sales targets by 22%

## Layout
- `src/` application code
- `tests/` unit tests
