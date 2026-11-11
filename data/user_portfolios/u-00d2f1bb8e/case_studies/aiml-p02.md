---
project: aiml-p02
client_industry: SaaS
date: 2025-06
duration_weeks: 6
repo: triage-agent
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Case study: Ticketly

**Situation.** First-response times above 9 hours because every ticket was triaged by hand.
**Task.** Deliver a production-ready fix within 6 weeks for a saas business.
**Action.** An agent that classifies intent, pulls account context through the Zendesk API and drafts a reply for a human to approve, with long-running enrichment pushed to a worker queue. Tooling: Python, LangChain, Zendesk API, PostgreSQL.
**Result.** median first response dropped from 9.2 h to 47 min; 63% of drafted replies sent with no edits.
