---
project: da-p02
client_industry: SaaS
date: 2025-03
duration_weeks: 6
repo: formflow-dbt
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Case study: Formflow

**Situation.** Every analyst wrote their own revenue query and none of them matched.
**Task.** Deliver a production-ready fix within 6 weeks for a saas business.
**Action.** A tested dbt project with staging, intermediate and mart layers and one definition of revenue. Tooling: tested, version-controlled SQL transformations, Snowflake, SQL, Fivetran.
**Result.** one certified revenue metric replaced 9 conflicting queries; data test coverage on all mart models.
