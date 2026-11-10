<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# booking-gateway

A GraphQL gateway with batched resolvers and response caching in front of the legacy services.

**Stack:** TS, Apollo Server, Node, containers, AWS ECS

## Why
Built for a travel client where the mobile app made 14 REST calls to render one booking screen.

## Quick start
```bash
npm install && npm run dev
```

## Results in production
- booking screen load time from 3.8 s to 1.1 s
- API calls per screen from 14 to 1

## Layout
- `src/` application code
- `tests/` unit tests
