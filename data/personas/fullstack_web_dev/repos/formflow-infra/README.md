<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# formflow-infra

Containerised the app, wrote Terraform for the AWS stack and a GitHub Actions pipeline with blue-green releases.

**Stack:** containers, GitHub Actions, Terraform, Amazon Web Services

## Why
Built for a saas client where deploys were manual SSH sessions that broke production every few weeks.

## Quick start
```bash
pip install -r requirements.txt && python -m formflow_infra.core data/sample.jsonl
```

## Results in production
- deploy time from 45 minutes to 8 minutes
- no failed deploy reached users in six months

## Layout
- `src/` application code
- `tests/` unit tests
