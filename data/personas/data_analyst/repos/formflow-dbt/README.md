<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# formflow-dbt

A tested dbt project with staging, intermediate and mart layers and one definition of revenue.

**Stack:** dbt, Snowflake, SQL, Fivetran

## Why
Built for a saas client where every analyst wrote their own revenue query and none of them matched.

## Quick start
```bash
pip install -r requirements.txt && python -m formflow_dbt.core data/sample.jsonl
```

## Results in production
- one certified revenue metric replaced 9 conflicting queries
- data test coverage on all mart models

## Layout
- `src/` application code
- `tests/` unit tests
