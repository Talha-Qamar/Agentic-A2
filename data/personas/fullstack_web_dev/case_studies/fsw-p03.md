---
project: fsw-p03
client_industry: Food Delivery
date: 2024-12
duration_weeks: 6
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# Khaana Now: real-time in 2024

When Khaana Now reached out, customers phoned support to ask where their rider was. I spent 6 weeks on it. The heart of the solution was rider apps stream GPS over WebSockets, fanned out through Redis to customer apps with live ETA, built with TypeScript, one app for both iOS and Android, Node.js, Socket.IO, Redis.

The part I am proudest of: 'where is my order' calls down 46%. Location updates delivered under 1 s p95.
