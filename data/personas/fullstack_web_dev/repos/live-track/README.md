<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# live-track

Rider apps stream GPS over WebSockets, fanned out through Redis to customer apps with live ETA.

**Stack:** TS, React Native, Node, Socket.IO, an in-memory cache

## Why
Built for a food delivery client where customers phoned support to ask where their rider was.

## Quick start
```bash
npm install && npm run dev
```

## Results in production
- 'where is my order' calls down 46%
- location updates delivered under 1 s p95

## Layout
- `src/` application code
- `tests/` unit tests
