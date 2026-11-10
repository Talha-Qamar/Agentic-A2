---
project: aiml-p18
client_industry: AI Services
date: 2024-09
duration_weeks: 5
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# LabelForge: data labelling in 2024

When LabelForge reached out, annotators labelled every image from scratch. I spent 5 weeks on it. The heart of the solution was a Label Studio backend that pre-annotates with the latest model and routes uncertain items to senior annotators, built with Python, Label Studio, a Python web API, PostgreSQL.

The part I am proudest of: labelling throughput up 2.6x. Inter-annotator disagreement down 18%.
