---
project: aiml-p06
client_industry: E-commerce
date: 2024-08
duration_weeks: 6
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Threadline: semantic search in 2024

When Threadline reached out, keyword search returned nothing for queries like 'summer wedding outfit under 5k'. I spent 6 weeks on it. The heart of the solution was hybrid lexical plus dense retrieval with a cross-encoder reranker and price filters parsed from the query, built with Python, sentence-transformers, Elasticsearch, a Python web API.

The part I am proudest of: search conversion up 17% in an A/B test. Zero-result queries down from 12% to 3%.
