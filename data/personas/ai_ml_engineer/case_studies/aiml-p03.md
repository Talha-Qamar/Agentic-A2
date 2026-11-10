---
project: aiml-p03
client_industry: Retail
date: 2024-11
duration_weeks: 9
---
<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# FreshCart: time series in 2024

When FreshCart reached out, stock-outs on fresh produce and 11% waste from over-ordering. I spent 9 weeks on it. The heart of the solution was store-by-SKU gradient-boosted forecasts with holiday and weather features, retrained nightly by an Airflow DAG, built with Python, LightGBM, cleaning data in Python, Airflow, AWS.

The part I am proudest of: forecast MAPE improved from 31% to 18%. Produce waste down 4 percentage points in the pilot region.
