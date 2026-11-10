---
project: fsw-p13
client_industry: E-commerce
date: 2023-05
duration_weeks: 3
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Performance rescue for a slow Laravel ecommerce site

## The problem
GharKaSaman (E-commerce) came to me because checkout took 12 seconds during sales and the database CPU hit 100%.

## What I built
Over 3 weeks I delivered profiled queries, added indexes, removed N+1 loops and cached catalogue pages in Redis. The work used PHP, our existing PHP application, MySQL, Redis.

## Results
- checkout time from 12 s to 1.6 s
- database CPU at peak from 100% to 35%

> "Saved our sale weekend." - GharKaSaman team
