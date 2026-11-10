<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# stripe-billing-kit

Stripe Billing with plan upgrades, proration, dunning emails and webhook handlers that are safe to retry.

**Stack:** TS, React, Node, Stripe, Express

## Why
Built for a edtech client where manual invoicing and failed card payments nobody noticed.

## Quick start
```bash
npm install && npm run dev
```

## Results in production
- involuntary churn down 23% after dunning
- zero duplicate charges since launch

## Layout
- `src/` application code
- `tests/` unit tests
