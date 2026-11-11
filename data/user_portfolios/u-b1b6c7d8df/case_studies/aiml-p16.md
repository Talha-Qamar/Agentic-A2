---
project: aiml-p16
client_industry: Travel
date: 2025-12
duration_weeks: 3
repo: agent-redteam
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Prompt-injection hardening for a customer-facing agent

## The problem
Safarnama (Travel) came to me because a booking agent could be talked into issuing refunds by instructions hidden in emails.

## What I built
Over 3 weeks I delivered untrusted-content delimiting, tool permission tiers, a red-team suite of 150 attacks and PII masking in logs. The work used Python, a stateful agent workflow with branching steps and a human review step, Guardrails, pytest.

## Results
- attack success rate fell from 34% to 3% on the red-team suite
- no PII in traces after the rollout audit

> "They broke our agent first, then fixed it." - Safarnama team
