---
project: fsw-p08
client_industry: Travel
date: 2024-03
duration_weeks: 9
repo: booking-gateway
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Case study: Safarnama

**Situation.** The mobile app made 14 REST calls to render one booking screen.
**Task.** Deliver a production-ready fix within 9 weeks for a travel business.
**Action.** A GraphQL gateway with batched resolvers and response caching in front of the legacy services. Tooling: TypeScript, Apollo Server, Node.js, containerised deployment, AWS ECS.
**Result.** booking screen load time from 3.8 s to 1.1 s; API calls per screen from 14 to 1.
