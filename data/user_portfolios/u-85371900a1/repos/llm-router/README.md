<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# llm-router

Semantic caching, routing short requests to a small self-hosted model and tracing every call with token and cost attributes.

**Stack:** Python, vLLM, an in-memory cache, OpenTelemetry

## Why
Built for a saas client where monthly LLM spend had tripled and p95 latency was over 9 seconds.

## Quick start
```bash
pip install -r requirements.txt && python -m llm_router.core data/sample.jsonl
```

## Results in production
- API spend down 58%
- p95 latency from 9.4 s to 2.1 s

## Layout
- `src/` application code
- `tests/` unit tests
