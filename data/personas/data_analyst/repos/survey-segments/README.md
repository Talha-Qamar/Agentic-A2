<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# survey-segments

Weighted responses, factor analysis on attitude questions and k-means segments with personas.

**Stack:** Python, pandas, sklearn, spreadsheets

## Why
Built for a market research client where a 5,000-respondent survey needed segments the client could act on.

## Quick start
```bash
pip install -r requirements.txt && python -m survey_segments.core data/sample.jsonl
```

## Results in production
- five segments adopted in the client's brand strategy
- report delivered three days ahead of deadline

## Layout
- `src/` application code
- `tests/` unit tests
