"""Derive market statistics and a historical job sample from REAL Upwork data.

Source: "Upwork Job Postings Dataset 2024 (50K Records)" by asaniczka on Kaggle,
ODC Attribution License (ODC-By 1.0).
https://www.kaggle.com/datasets/asaniczka/upwork-job-postings-dataset-2024-50k-records

Usage:
    python data/generator/build_market.py /path/to/upwork-jobs.csv

Outputs (committed, small, attributed):
    gigsim/seed_data/market_stats.json     per-category price percentiles
    gigsim/seed_data/historical_jobs.jsonl 1,500 real job posts (persona-relevant categories)
"""
from __future__ import annotations

import csv
import html
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "gigsim" / "seed_data"

RELEVANT = {
    "ai_ml_engineer": ["Machine Learning", "AI Apps & Integration", "Scripting & Automation", "Data Science",
                       "Deep Learning", "Natural Language Processing", "AI Chatbot Development", "Computer Vision"],
    "fullstack_web_dev": ["Full Stack Development", "Front-End Development", "Back-End Development", "Web Development",
                          "Ecommerce Website Development", "Web Design", "Mobile App Development", "DevOps Engineering",
                          "CMS Development"],
    "data_analyst": ["Data Analytics", "Data Visualization", "Financial Analysis & Modeling", "Data Engineering",
                     "Data Mining", "Data Processing", "Business Intelligence", "Data Extraction", "Market Research"],
}


def parse_row(r: dict) -> dict | None:
    d = r["description"]
    m_cat = re.search(r"Category:\s*(.*?)Skills:", d) or re.search(r"Category:\s*(.*?)Country:", d)
    m_sk = re.search(r"Skills:(.*?)Skills:", d)
    body = re.split(r"(Budget:|Hourly Range:|Posted On:)", d)[0]
    body = html.unescape(body).replace("\xa0", " ").strip()
    cat = m_cat.group(1).strip() if m_cat else None
    skills = [s.strip() for s in m_sk.group(1).split(",")] if m_sk else []
    skills = [s for s in skills if s]
    hourly = r["is_hourly"] == "True"
    try:
        lo = float(r["hourly_low"]) if r["hourly_low"] else None
        hi = float(r["hourly_high"]) if r["hourly_high"] else None
        budget = float(r["budget"]) if r["budget"] else None
    except ValueError:
        return None
    if not cat or len(body) < 80:
        return None
    return dict(title=html.unescape(r["title"]).strip(), description=body, category=cat, skills=skills,
                is_hourly=hourly, hourly_low=lo, hourly_high=hi, budget=budget, country=r["country"] or None,
                published=r["published_date"], source_url=r["link"])


def pct(vals: list[float]) -> dict:
    a = np.array(vals, dtype=float)
    return {"n": int(a.size), "p10": float(np.percentile(a, 10)), "p25": float(np.percentile(a, 25)),
            "p50": float(np.percentile(a, 50)), "p75": float(np.percentile(a, 75)), "p90": float(np.percentile(a, 90))}


def main(csv_path: str) -> None:
    csv.field_size_limit(10**9)
    rows = [x for x in (parse_row(r) for r in csv.DictReader(open(csv_path, encoding="utf-8"))) if x]
    hourly_by_cat, fixed_by_cat = defaultdict(list), defaultdict(list)
    hourly_all, fixed_all = [], []
    for x in rows:
        if x["is_hourly"] and x["hourly_low"] and x["hourly_high"] and 3 <= x["hourly_high"] <= 300:
            mid = (x["hourly_low"] + x["hourly_high"]) / 2
            hourly_by_cat[x["category"]].append(mid)
            hourly_all.append(mid)
        elif (not x["is_hourly"]) and x["budget"] and 5 <= x["budget"] <= 100000:
            fixed_by_cat[x["category"]].append(x["budget"])
            fixed_all.append(x["budget"])
    stats = {
        "source": "Kaggle: asaniczka/upwork-job-postings-dataset-2024-50k-records (ODC-By 1.0)",
        "rows_parsed": len(rows),
        "hourly_all": pct(hourly_all), "fixed_all": pct(fixed_all),
        "hourly": {c: pct(v) for c, v in hourly_by_cat.items() if len(v) >= 25},
        "fixed": {c: pct(v) for c, v in fixed_by_cat.items() if len(v) >= 25},
        "persona_categories": RELEVANT,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "market_stats.json").write_text(json.dumps(stats, indent=1))

    rng = random.Random(2026)
    relevant_cats = {c for cats in RELEVANT.values() for c in cats}
    pool = [x for x in rows if x["category"] in relevant_cats]
    rng.shuffle(pool)
    seen, sample = set(), []
    for x in pool:
        key = x["title"].lower()
        if key in seen:
            continue
        seen.add(key)
        sample.append(x)
        if len(sample) == 1500:
            break
    with open(OUT / "historical_jobs.jsonl", "w") as f:
        for i, x in enumerate(sample):
            x = dict(x, job_id=f"hist-{i:04d}", real_data=True)
            f.write(json.dumps(x) + "\n")
    print(f"parsed={len(rows)} hourly={len(hourly_all)} fixed={len(fixed_all)} sample={len(sample)}")
    for c in sorted(relevant_cats):
        h, fx = stats["hourly"].get(c), stats["fixed"].get(c)
        print(f"{c:35s} hourly p50={h['p50'] if h else None}  fixed p50={fx['p50'] if fx else None}")


if __name__ == "__main__":
    main(sys.argv[1])
