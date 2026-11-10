---
project: fsw-p09
client_industry: SaaS
date: 2025-06
duration_weeks: 3
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Formflow: DevOps in 2025

When Formflow reached out, deploys were manual SSH sessions that broke production every few weeks. I spent 3 weeks on it. The heart of the solution was containerised the app, wrote Terraform for the AWS stack and a GitHub Actions pipeline with blue-green releases, built with containerised deployment, GitHub Actions, Terraform, AWS.

The part I am proudest of: deploy time from 45 minutes to 8 minutes. No failed deploy reached users in six months.
