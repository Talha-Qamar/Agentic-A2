<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# a11y-fixes

Fixed semantic markup, keyboard flows and contrast, then added automated accessibility checks to CI.

**Stack:** React, TS, axe-core, Playwright

## Why
Built for a government client where a citizen portal failed a WCAG 2.1 AA audit with 212 issues.

## Quick start
```bash
npm install && npm run dev
```

## Results in production
- audit issues from 212 to 6
- screen-reader task completion up from 40% to 95%

## Layout
- `src/` application code
- `tests/` unit tests
