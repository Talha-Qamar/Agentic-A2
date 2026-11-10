<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# pharmacy-forecast

Weekly SKU forecasts with Ramadan and flu-season effects, exported to the purchasing team's Excel template.

**Stack:** Python, Prophet, SQL, spreadsheets

## Why
Built for a healthcare client where pharmacies ran out of seasonal medicines during flu season.

## Quick start
```bash
pip install -r requirements.txt && python -m pharmacy_forecast.core data/sample.jsonl
```

## Results in production
- stock-outs on top 200 SKUs down 35%
- forecast error (WAPE) from 28% to 16%

## Layout
- `src/` application code
- `tests/` unit tests
