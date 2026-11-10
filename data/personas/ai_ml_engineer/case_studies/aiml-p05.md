---
project: aiml-p05
client_industry: EdTech
date: 2025-10
duration_weeks: 4
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Case study: Essayly

**Situation.** Prompt changes shipped weekly with no way to tell whether feedback quality got worse.
**Task.** Deliver a production-ready fix within 4 weeks for a edtech business.
**Action.** A golden set of 400 graded essays, an LLM judge calibrated against teacher labels and a CI gate on every prompt change. Tooling: Python, pytest, LangSmith, the OpenAI API.
**Result.** judge agreement with teachers of Cohen's kappa 0.71; caught two regressions before release in the first month.
