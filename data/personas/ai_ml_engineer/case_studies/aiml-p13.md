---
project: aiml-p13
client_industry: SaaS
date: 2025-11
duration_weeks: 3
repo: llm-router
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# LLM cost and latency optimisation for a writing tool

## The problem
Draftwell (SaaS) came to me because monthly LLM spend had tripled and p95 latency was over 9 seconds.

## What I built
Over 3 weeks I delivered semantic caching, routing short requests to a small self-hosted model and tracing every call with token and cost attributes. The work used Python, fast self-hosted LLM inference, Redis, OpenTelemetry.

## Results
- API spend down 58%
- p95 latency from 9.4 s to 2.1 s

> "Paid for itself in the first month." - Draftwell team
