<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# clause-rag

A retrieval pipeline that chunks contracts by clause heading, retrieves with hybrid search and forces every answer to quote the clause it relies on.

**Stack:** Python, LangGraph, a FastAPI service, Qdrant, GPT-4-class models

## Why
Built for a legal client where lawyers spent hours locating indemnity and termination clauses across 300-page vendor contracts.

## Quick start
```bash
pip install -r requirements.txt && python -m clause_rag.core data/sample.jsonl
```

## Results in production
- clause lookup time fell from ~40 minutes to under 2 minutes
- answer citation accuracy of 94% on a 120-question review set

## Layout
- `src/` application code
- `tests/` unit tests
