---
project: aiml-p04
client_industry: FinTech
date: 2025-03
duration_weeks: 5
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Invoice extraction pipeline with vision-language models

## The problem
LedgerLoop (FinTech) came to me because an AP team keyed 2,000 supplier invoices a month by hand.

## What I built
Over 5 weeks I delivered a fine-tuned document-understanding model that outputs JSON line items, validated against purchase orders before posting. The work used Python, deep learning model training, Donut, FastAPI, Docker.

## Results
- field-level F1 of 0.93 on held-out suppliers
- manual keying reduced by roughly 70%

> "Handled the ugly scanned invoices we were sure would break it." - LedgerLoop team
