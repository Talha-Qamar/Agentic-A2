<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# teamboard-events

Designed an event taxonomy, fixed tracking gaps and built activation and retention funnels.

**Stack:** Mixpanel, SQL, Python, Segment

## Why
Built for a saas client where the product team could not say where trial users dropped off.

## Quick start
```bash
pip install -r requirements.txt && python -m teamboard_events.core data/sample.jsonl
```

## Results in production
- found an onboarding step losing 38% of trials
- trial-to-paid conversion up from 9% to 13%

## Layout
- `src/` application code
- `tests/` unit tests
