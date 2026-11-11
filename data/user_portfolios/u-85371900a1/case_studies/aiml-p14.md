---
project: aiml-p14
client_industry: Media
date: 2023-07
duration_weeks: 6
repo: urdu-ner
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Case study: Khabar Labs

**Situation.** No off-the-shelf model recognised people and places in Urdu news reliably.
**Task.** Deliver a production-ready fix within 6 weeks for a media business.
**Action.** Fine-tuned a multilingual transformer on 6k hand-labelled sentences with active learning to pick what to label next. Tooling: Python, spaCy, Hugging Face Transformers.
**Result.** entity F1 of 0.86, up from 0.61 for the multilingual baseline; labelling budget cut by about 40% through active learning.
