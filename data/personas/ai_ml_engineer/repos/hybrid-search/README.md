<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# hybrid-search

Hybrid lexical plus dense retrieval with a cross-encoder reranker and price filters parsed from the query.

**Stack:** Python, sentence-transformers, Elasticsearch, a FastAPI service

## Why
Built for a e-commerce client where keyword search returned nothing for queries like 'summer wedding outfit under 5k'.

## Quick start
```bash
pip install -r requirements.txt && python -m hybrid_search.core data/sample.jsonl
```

## Results in production
- search conversion up 17% in an A/B test
- zero-result queries down from 12% to 3%

## Layout
- `src/` application code
- `tests/` unit tests
