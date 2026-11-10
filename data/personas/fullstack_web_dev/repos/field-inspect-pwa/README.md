<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# field-inspect-pwa

An offline-first PWA that queues inspections and photos locally and syncs when back online.

**Stack:** TS, React, IndexedDB, Node, MongoDB

## Why
Built for a construction client where inspectors lost forms when the site had no signal.

## Quick start
```bash
npm install && npm run dev
```

## Results in production
- lost inspection reports dropped to zero
- report turnaround from 3 days to same day

## Layout
- `src/` application code
- `tests/` unit tests
