<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# invoice-vlm

A fine-tuned document-understanding model that outputs JSON line items, validated against purchase orders before posting.

**Stack:** Python, torch, Donut, a FastAPI service, containers

## Why
Built for a fintech client where an AP team keyed 2,000 supplier invoices a month by hand.

## Quick start
```bash
pip install -r requirements.txt && python -m invoice_vlm.core data/sample.jsonl
```

## Results in production
- field-level F1 of 0.93 on held-out suppliers
- manual keying reduced by roughly 70%

## Layout
- `src/` application code
- `tests/` unit tests
