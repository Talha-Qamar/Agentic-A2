<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# clinic-api

A booking API with slot locking, SMS reminders sent from a worker queue and an admin panel for front desks.

**Stack:** Python, Django, Django REST Framework, Postgres, Celery

## Why
Built for a healthcare client where double-booked appointments and no reminders, so 30% of patients no-showed.

## Quick start
```bash
pip install -r requirements.txt && python -m clinic_api.core data/sample.jsonl
```

## Results in production
- no-show rate from 30% to 12%
- double bookings eliminated

## Layout
- `src/` application code
- `tests/` unit tests
