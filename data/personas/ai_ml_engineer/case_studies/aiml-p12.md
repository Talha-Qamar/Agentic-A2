---
project: aiml-p12
client_industry: Media
date: 2024-02
duration_weeks: 8
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Sunwave Audio: recommender systems in 2024

When Sunwave Audio reached out, new listeners churned because the home feed showed only the global top 20. I spent 8 weeks on it. The heart of the solution was matrix-factorisation recommendations with a content-based fallback for cold-start users, served from a Redis cache, built with Python, implicit, Spark, an in-memory cache in front of the database, FastAPI.

The part I am proudest of: 7-day listener retention up 9%. Home-feed click-through up 22%.
