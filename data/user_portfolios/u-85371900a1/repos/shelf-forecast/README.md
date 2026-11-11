<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# shelf-forecast

Store-by-SKU gradient-boosted forecasts with holiday and weather features, retrained nightly by an Airflow DAG.

**Stack:** Python, LightGBM, pandas, Airflow, Amazon Web Services

## Why
Built for a retail client where stock-outs on fresh produce and 11% waste from over-ordering.

## Quick start
```bash
pip install -r requirements.txt && python -m shelf_forecast.core data/sample.jsonl
```

## Results in production
- forecast MAPE improved from 31% to 18%
- produce waste down 4 percentage points in the pilot region

## Layout
- `src/` application code
- `tests/` unit tests
