---
project: da-p07
client_industry: E-commerce
date: 2023-10
duration_weeks: 4
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Web scraping-free price monitoring with official APIs

## The problem
PriceWatch.pk (E-commerce) came to me because manual competitor price checks covered only 50 products.

## What I built
Over 4 weeks I delivered a daily pipeline that pulls partner product feeds through their official APIs, validates them and charts price moves. The work used Python, scheduled pipelines that run every night, PostgreSQL, Metabase.

## Results
- coverage from 50 to 8,000 products
- pricing decisions reviewed daily instead of monthly

> "Solid pipeline that runs every morning without babysitting." - PriceWatch.pk team
