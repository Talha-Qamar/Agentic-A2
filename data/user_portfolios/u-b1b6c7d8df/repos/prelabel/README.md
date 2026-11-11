<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# prelabel

A Label Studio backend that pre-annotates with the latest model and routes uncertain items to senior annotators.

**Stack:** Python, Label Studio, a FastAPI service, Postgres

## Why
Built for a ai services client where annotators labelled every image from scratch.

## Quick start
```bash
pip install -r requirements.txt && python -m prelabel.core data/sample.jsonl
```

## Results in production
- labelling throughput up 2.6x
- inter-annotator disagreement down 18%

## Layout
- `src/` application code
- `tests/` unit tests
