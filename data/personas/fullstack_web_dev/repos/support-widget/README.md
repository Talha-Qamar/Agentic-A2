<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# support-widget

An embedded chat widget with streaming answers grounded in help articles and a handoff to human support.

**Stack:** TS, Next, GPT-4-class models, Postgres, pgvector

## Why
Built for a saas client where users could not find answers in 300 help-centre articles.

## Quick start
```bash
npm install && npm run dev
```

## Results in production
- support tickets down 29%
- answer helpfulness rated 4.4/5 by users

## Layout
- `src/` application code
- `tests/` unit tests
