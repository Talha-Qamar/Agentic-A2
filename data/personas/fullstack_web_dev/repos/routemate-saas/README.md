<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# routemate-saas

A single multi-tenant Next.js app with tenant-scoped queries, role-based permissions and self-serve onboarding.

**Stack:** TS, Next, Node, Postgres, Prisma

## Why
Built for a logistics client where each customer got a hand-patched copy of the app and onboarding took a week.

## Quick start
```bash
npm install && npm run dev
```

## Results in production
- new customer onboarding from 5 days to 20 minutes
- infrastructure cost per tenant down 60%

## Layout
- `src/` application code
- `tests/` unit tests
