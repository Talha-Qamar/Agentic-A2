"""Render the SYNTHETIC persona corpora into data/personas/<persona>/.

Deterministic (seeded).  Run:  python data/generator/build_personas.py

Per persona it writes
    profile.json              rates, categories, headline (no project facts)
    cv.pdf                    PDF CV (terse bullets, different vocabulary)
    case_studies/*.md         narrative case studies in three different styles (15 of 18 projects)
    repos/<slug>/README.md    technical READMEs; some deliberately thin
    repos/<slug>/src/*        code files - the only place "implicit" skills appear
    reviews.json              client reviews (+ unrelated small gigs as noise)
    past_proposals.jsonl      ~150 past proposals labelled won / replied / ignored
and a gold file outside the agent's reach:
    evals/datasets/gold/<persona>_corpus_manifest.json  document -> project mapping
"""
from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from jobgen import INDUSTRIES, sample_requirements, sigmoid  # noqa: E402
from persona_bank import PERSONAS, PROJECTS  # noqa: E402
from skills import IMPLIED, canon, prose  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "personas"
GOLD = ROOT / "evals" / "datasets" / "gold"

SYNTH_BANNER = "<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->"

PY_IMPORTS = {
    "pydantic": "from pydantic import BaseModel, Field", "pytest": "import pytest", "asyncio": "import asyncio",
    "celery": "from celery import shared_task", "redis": "import redis", "tenacity": "from tenacity import retry, stop_after_attempt, wait_exponential",
    "scikit-learn": "from sklearn.model_selection import TimeSeriesSplit", "boto3": "import boto3", "optuna": "import optuna",
    "transformers": "from transformers import AutoProcessor, VisionEncoderDecoderModel", "pdf2image": "from pdf2image import convert_from_path",
    "pandas": "import pandas as pd", "scipy": "from scipy import stats", "jinja2": "from jinja2 import Template",
    "faiss": "import faiss", "numpy": "import numpy as np", "locust": "from locust import HttpUser, task",
    "ffmpeg": "import ffmpeg", "pydub": "from pydub import AudioSegment", "imbalanced-learn": "from imblearn.over_sampling import SMOTE",
    "sqlalchemy": "from sqlalchemy import create_engine, text", "tiktoken": "import tiktoken", "onnxruntime": "import onnxruntime as ort",
    "albumentations": "import albumentations as A", "tensorrt": "import tensorrt as trt", "msal": "import msal",
    "pgvector": "from pgvector.psycopg import register_vector", "fastapi": "from fastapi import FastAPI, Depends",
    "pyspark": "from pyspark.sql import SparkSession", "annoy": "from annoy import AnnoyIndex", "httpx": "import httpx",
    "prometheus-client": "from prometheus_client import Histogram", "datasets": "from datasets import load_dataset",
    "seqeval": "from seqeval.metrics import f1_score", "torch": "import torch", "lightgbm": "import lightgbm as lgb",
    "shap": "import shap", "presidio": "from presidio_analyzer import AnalyzerEngine", "regex": "import regex",
    "pydicom": "import pydicom", "grad-cam": "from pytorch_grad_cam import GradCAM", "redis pub/sub": "import redis",
    "channels": "from channels.generic.websocket import AsyncWebsocketConsumer", "geodjango": "from django.contrib.gis.db import models as gis",
    "pytest-django": "import pytest", "drf-spectacular": "from drf_spectacular.utils import extend_schema",
    "lifelines": "from lifelines import KaplanMeierFitter", "statsmodels": "import statsmodels.formula.api as smf",
    "seaborn": "import seaborn as sns", "holidays": "import holidays", "requests": "import requests",
    "great expectations": "import great_expectations as gx", "postgis": "# SQL below uses PostGIS ST_DWithin",
    "geohash": "import pygeohash as pgh", "cuped": "# CUPED variance reduction (see adjust_with_cuped)",
    "shapely": "from shapely.geometry import Point", "h3": "import h3", "matplotlib": "import matplotlib.pyplot as plt",
    "k-means": "from sklearn.cluster import KMeans", "factor analysis": "from sklearn.decomposition import FactorAnalysis",
    "log-log regression": "import statsmodels.formula.api as smf", "causal inference": "# double ML style controls for promotions",
    "recharts": "", "cron": "# scheduled via cron: 0 8 * * MON",
}
TS_IMPORTS = {
    "zod": 'import { z } from "zod";', "tRPC": 'import { initTRPC } from "@trpc/server";', "casl": 'import { AbilityBuilder } from "@casl/ability";',
    "react-query": 'import { useQuery } from "@tanstack/react-query";', "dataloader": 'import DataLoader from "dataloader";',
    "mapbox-gl": 'import mapboxgl from "mapbox-gl";', "expo": 'import * as Location from "expo-location";',
    "graphql": 'import { gql } from "graphql-tag";', "jest": 'import { describe, it, expect } from "@jest/globals";',
    "jest-axe": 'import { axe } from "jest-axe";', "storybook": 'import type { Meta } from "@storybook/react";',
    "workbox": 'import { registerRoute } from "workbox-routing";', "vite": 'import { defineConfig } from "vite";',
    "recharts": 'import { LineChart, Line } from "recharts";', "k6": 'import http from "k6/http";',
    "vercel ai sdk": 'import { streamText } from "ai";', "webauthn": 'import { generateRegistrationOptions } from "@simplewebauthn/server";',
    "next-sitemap": '/** @type {import("next-sitemap").IConfig} */', "redis": 'import { createClient } from "redis";',
}


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def is_python(p: dict) -> bool:
    return any(s in p["stack"] for s in ("Python", "Django", "FastAPI", "PyTorch")) or not any(
        s in p["stack"] for s in ("TypeScript", "React", "Next.js", "Node.js", "React Native", "PHP", "Laravel"))


def code_files(p: dict, rng: random.Random) -> dict[str, str]:
    files: dict[str, str] = {}
    name = (p["repo"] or slug(p["title"])).replace("-", "_")
    if is_python(p):
        imports = [PY_IMPORTS.get(i.lower(), PY_IMPORTS.get(i, "")) or f"# relies on {i}" for i in p["implicit"]]
        body = f'''"""{p["repo"]}: core module (synthetic sample code)."""
{chr(10).join(imports)}

CONFIG = {{"project": "{p['repo']}", "retries": 3, "batch_size": {rng.choice([16, 32, 64, 128])}}}


def load_records(path: str) -> list[dict]:
    """Load raw records; malformed rows are skipped and counted."""
    rows, bad = [], 0
    with open(path) as fh:
        for line in fh:
            try:
                rows.append(__import__("json").loads(line))
            except ValueError:
                bad += 1
    return rows


def run(path: str) -> dict:
    records = load_records(path)
    # {p["approach"][:90]}
    return {{"n": len(records), "status": "ok"}}
'''
        files[f"src/{name}/core.py"] = body
        if any(t in p["tags"] for t in ("background jobs",)) or "celery" in [i.lower() for i in p["implicit"]]:
            files[f"src/{name}/tasks.py"] = f'''from celery import shared_task


@shared_task(bind=True, max_retries=3, acks_late=True)
def process_item(self, item_id: str) -> str:
    """Long-running enrichment executed by the worker, not the web request."""
    return item_id
'''
        files["tests/test_core.py"] = f"from {name}.core import run\n\n\ndef test_run_empty(tmp_path):\n    f = tmp_path / 'x.jsonl'\n    f.write_text('')\n    assert run(str(f))['n'] == 0\n"
        files["requirements.txt"] = "\n".join(sorted({s.lower().replace(" ", "-") for s in p["stack"] + p["implicit"]
                                                      if s.lower() not in ("python", "sql", "aws")})) + "\n"
    else:
        imports = [TS_IMPORTS.get(i, TS_IMPORTS.get(i.lower(), "")) or f"// relies on {i}" for i in p["implicit"]]
        files["src/index.ts"] = f'''// {p["repo"]}: entry point (synthetic sample code)
{chr(10).join(imports)}

export interface Config {{ project: string; retries: number }}
export const config: Config = {{ project: "{p['repo']}", retries: 3 }};

// {p["approach"][:90]}
export async function handler(input: unknown): Promise<{{ ok: boolean }}> {{
  if (!input) throw new Error("empty input");
  return {{ ok: true }};
}}
'''
        deps = {s.lower().replace(" ", "-"): "latest" for s in p["stack"] + p["implicit"]
                if s not in ("TypeScript",) and not s[0].isupper()}
        files["package.json"] = json.dumps({"name": p["repo"], "private": True, "dependencies": deps}, indent=2)
    return files


def readme(p: dict, rng: random.Random, thin: bool) -> str:
    stack = ", ".join(prose(s, 1) for s in p["stack"])
    if thin:  # README that looks irrelevant on its own; the code tells the real story
        return f"""{SYNTH_BANNER}
# {p['repo']}

Internal tooling. See `src/` for details.

## Setup
```bash
make install && make run
```
"""
    lang = "python" if is_python(p) else "ts"
    return f"""{SYNTH_BANNER}
# {p['repo']}

{p['approach'][0].upper() + p['approach'][1:]}.

**Stack:** {stack}

## Why
Built for a {p['industry'].lower()} client where {p['problem']}.

## Quick start
```bash
{"pip install -r requirements.txt && python -m " + p['repo'].replace('-', '_') + ".core data/sample.jsonl" if lang == "python" else "npm install && npm run dev"}
```

## Results in production
{chr(10).join('- ' + o for o in p['outcomes'])}

## Layout
- `src/` application code
- `tests/` unit tests
"""


def case_study(p: dict, style: int, persona: str) -> str:
    stack_named = [s for s in p["stack"]]
    # one named skill is replaced by an implied description to defeat exact keyword match
    hidden = None
    for s in stack_named:
        if canon(s) in IMPLIED and canon(s) not in ("python",):
            hidden = s
            break
    def mention(s: str) -> str:
        if s == hidden:
            return IMPLIED[canon(s)][0]
        return prose(s, 0)
    stack_txt = ", ".join(mention(s) for s in stack_named)
    repo_line = f"repo: {p['repo']}\n" if p["repo"] else ""
    fm = f"---\nproject: {p['id']}\nclient_industry: {p['industry']}\ndate: {p['date']}\nduration_weeks: {p['weeks']}\n{repo_line}---\n"
    if style == 0:
        return f"""{fm}{SYNTH_BANNER}
# {p['title']}

## The problem
{p['client']} ({p['industry']}) came to me because {p['problem']}.

## What I built
Over {p['weeks']} weeks I delivered {p['approach']}. The work used {stack_txt}.

## Results
{chr(10).join('- ' + o for o in p['outcomes'])}

> "{p['review'][0].upper() + p['review'][1:]}." - {p['client']} team
"""
    if style == 1:
        return f"""{fm}{SYNTH_BANNER}
# Case study: {p['client']}

**Situation.** {p['problem'][0].upper() + p['problem'][1:]}.
**Task.** Deliver a production-ready fix within {p['weeks']} weeks for a {p['industry'].lower()} business.
**Action.** {p['approach'][0].upper() + p['approach'][1:]}. Tooling: {stack_txt}.
**Result.** {'; '.join(p['outcomes'])}.
"""
    return f"""{fm}{SYNTH_BANNER}
# {p['client']}: {p['tags'][0]} in {p['date'][:4]}

When {p['client']} reached out, {p['problem']}. I spent {p['weeks']} weeks on it. The heart of the solution was {p['approach']}, built with {stack_txt}.

The part I am proudest of: {p['outcomes'][0]}. {p['outcomes'][1][0].upper() + p['outcomes'][1][1:]}.
"""


def cv_bullet(p: dict) -> str:
    stack = "/".join(prose(s, 2) for s in p["stack"][:3])
    return f"{p['date'][:4]} - {p['client']} ({p['industry']}): {p['tags'][0]} with {stack}; {p['outcomes'][0]}."


def write_cv_pdf(path: Path, persona: str, bullets: list[str]) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    prof = PERSONAS[persona]
    ss = getSampleStyleSheet()
    skills = sorted({prose(s, 2) for p in PROJECTS[persona] for s in p["stack"]})
    story = [Paragraph(prof["name"], ss["Title"]), Paragraph(prof["headline"], ss["Heading3"]),
             Paragraph(f"{prof['location']} - {prof['years']} years freelancing - SYNTHETIC PERSONA (GigBid assignment)", ss["Normal"]),
             Spacer(1, 8), Paragraph("Summary", ss["Heading2"]), Paragraph(prof["summary"], ss["Normal"]),
             Paragraph("Skills", ss["Heading2"]), Paragraph(", ".join(skills), ss["Normal"]),
             Paragraph("Selected experience", ss["Heading2"])]
    story += [Paragraph("- " + b, ss["Normal"]) for b in bullets]
    story += [Paragraph("Education", ss["Heading2"]), Paragraph(prof["education"], ss["Normal"])]
    SimpleDocTemplate(str(path), pagesize=A4, title=f"CV - {prof['name']}").build(story)


GENERIC_OPENINGS = [
    "Dear Hiring Manager, I am a passionate and highly skilled {role} with {years}+ years of experience.",
    "Hello, I have carefully read your job post and I am confident I am the perfect fit for this project.",
    "Hi there! I am an expert {role} and I can deliver top-notch quality work on time.",
    "Greetings! I am very interested in your project and I guarantee 100% satisfaction.",
]
SPECIFIC_OPENINGS = [
    "You need {need}. I built almost exactly that for {client} ({industry}), where {outcome}.",
    "{need_cap} is the hard part of this job. At {client} I solved the same problem: {outcome}.",
    "Your post mentions {need}; my most relevant work is a {industry} project where {outcome}.",
]
CLOSINGS = ["Happy to walk you through the code on a short call.", "I can start this week.",
            "Looking forward to hearing from you.", "I can share the repository on request."]


def proposals(persona: str, rng: random.Random, stats: dict, n: int = 150) -> list[dict]:
    prof = PERSONAS[persona]
    role = prof["headline"].split(":")[0].lower()
    projects = PROJECTS[persona]
    out = []
    for i in range(n):
        fit = rng.choices(["high", "partial", "low"], weights=[0.55, 0.3, 0.15])[0]
        reqs, meta = sample_requirements(rng, persona, rng.randint(2, 5), fit)
        req_skills = {r.skill for r in reqs}
        relevant = [p for p in projects if req_skills & {canon(s) for s in p["stack"] + p["implicit"] + p["tags"]}]
        specific = rng.random() < 0.5
        cite_relevant = relevant and rng.random() < 0.75
        cited = rng.sample(relevant, k=min(len(relevant), rng.randint(1, 2))) if cite_relevant else rng.sample(projects, k=rng.randint(1, 2))
        lead = cited[0]
        need = reqs[0].text[0].lower() + reqs[0].text[1:]
        if specific:
            opening = rng.choice(SPECIFIC_OPENINGS).format(need=need, need_cap=need[0].upper() + need[1:], client=lead["client"],
                                                          industry=lead["industry"].lower(), outcome=lead["outcomes"][0])
        else:
            opening = rng.choice(GENERIC_OPENINGS).format(role=role, years=prof["years"])
        body = " ".join(f"At {p['client']} I delivered {p['approach'].split(',')[0]}, and {p['outcomes'][rng.randint(0, 1)]}." for p in cited)
        plan = "My plan: " + "; ".join(f"({k + 1}) {s}" for k, s in enumerate(rng.sample(
            ["confirm scope and success metrics in a kickoff call", "ship a working slice in week one",
             "add tests and monitoring before handover", "document everything so your team can own it",
             "review progress with you twice a week"], k=3))) + "."
        long_form = rng.random() < 0.25
        filler = (" I am a hard worker, I am very communicative, and I always go the extra mile for my clients, "
                  "because client satisfaction is my top priority and I love what I do.") * (2 if long_form else 0)
        text = f"{opening}\n\n{body}{filler}\n\n{plan}\n\n{rng.choice(CLOSINGS)}"
        category = rng.choice(prof["categories"][:3])
        hourly_stats = stats["hourly"].get(category, stats["hourly_all"])
        rate = round(rng.uniform(prof["hourly_floor"], prof["target_rate"] * 1.4), 0)
        fair = hourly_stats["p25"] <= rate <= max(hourly_stats["p90"], prof["target_rate"] * 1.2)
        relevance = len({canon(s) for p in cited for s in p["stack"] + p["implicit"] + p["tags"]} & req_skills) / max(1, len(req_skills))
        # hidden generative rule for outcomes (documented in DATA_CARD.md)
        z = -1.4 + 1.5 * specific + 2.0 * relevance + 0.5 * fair - 0.9 * long_form - 0.8 * (not specific and "guarantee" in opening)
        u = rng.random()
        p_reply = sigmoid(z)
        outcome = "won" if u < p_reply * 0.45 else ("replied" if u < p_reply else "ignored")
        year = rng.choice(["2024", "2025"])
        out.append(dict(
            proposal_id=f"{persona[:4]}-prop-{i:03d}", date=f"{year}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            job_title=f"{reqs[0].text.split(' ')[-1].strip('.').title()} project for a {rng.choice(INDUSTRIES).lower()} client",
            job_category=category, job_requirements=[r.text for r in reqs], cited_projects=[p["id"] for p in cited],
            opening_style="specific" if specific else "generic", hourly_rate=rate, text=text, outcome=outcome,
            synthetic=True))
    return out


def reviews(persona: str, rng: random.Random) -> list[dict]:
    out = []
    for p in PROJECTS[persona]:
        out.append(dict(review_id=f"rev-{p['id']}", project=p["id"], client=p["client"], industry=p["industry"],
                        date=p["date"], rating=p["rating"], text=f"{p['review'][0].upper() + p['review'][1:]}. "
                        f"{rng.choice(['Great communication throughout.', 'Would hire again.', 'Delivered on time.', 'Very professional.'])}",
                        synthetic=True))
    for k in range(6):  # small unrelated gigs: noise without project evidence
        out.append(dict(review_id=f"rev-misc-{k}", project=None, client=f"Client {k + 1}", industry=rng.choice(INDUSTRIES),
                        date=f"202{rng.randint(3, 5)}-{rng.randint(1, 12):02d}", rating=round(rng.uniform(4.3, 5.0), 1),
                        text=rng.choice(["Quick fix, thanks!", "Helped with a small bug, fast turnaround.",
                                         "Good consultation call.", "Answered all my questions."]), synthetic=True))
    return out


def main() -> None:
    stats = json.loads((ROOT / "gigsim" / "seed_data" / "market_stats.json").read_text())
    GOLD.mkdir(parents=True, exist_ok=True)
    for persona in PERSONAS:
        rng = random.Random(f"gigbid-{persona}")
        base = OUT / persona
        (base / "case_studies").mkdir(parents=True, exist_ok=True)
        manifest = []
        projects = PROJECTS[persona]
        no_case_study = {projects[i]["id"] for i in rng.sample(range(len(projects)), 3)}
        thin_readme = {p["id"] for p in rng.sample([p for p in projects if p["repo"]], 2)}
        for i, p in enumerate(projects):
            if p["id"] not in no_case_study:
                fn = f"case_studies/{p['id']}.md"
                (base / fn).write_text(case_study(p, i % 3, persona))
                manifest.append({"path": fn, "type": "case_study", "project": p["id"]})
            if p["repo"]:
                rbase = base / "repos" / p["repo"]
                rbase.mkdir(parents=True, exist_ok=True)
                (rbase / "README.md").write_text(readme(p, rng, thin=p["id"] in thin_readme))
                manifest.append({"path": f"repos/{p['repo']}/README.md", "type": "readme", "project": p["id"]})
                for rel, content in code_files(p, rng).items():
                    fp = rbase / rel
                    fp.parent.mkdir(parents=True, exist_ok=True)
                    fp.write_text(content)
                    manifest.append({"path": f"repos/{p['repo']}/{rel}", "type": "code", "project": p["id"]})
        bullets = [cv_bullet(p) for p in sorted(projects, key=lambda x: x["date"], reverse=True)]
        write_cv_pdf(base / "cv.pdf", persona, bullets)
        manifest.append({"path": "cv.pdf", "type": "cv", "project": None})
        revs = reviews(persona, rng)
        (base / "reviews.json").write_text(json.dumps(revs, indent=1))
        props = proposals(persona, rng, stats)
        with open(base / "past_proposals.jsonl", "w") as f:
            for pr in props:
                f.write(json.dumps(pr) + "\n")
        prof = dict(PERSONAS[persona], persona_id=persona, synthetic=True)
        (base / "profile.json").write_text(json.dumps(prof, indent=1))
        (GOLD / f"{persona}_corpus_manifest.json").write_text(json.dumps(
            {"persona": persona, "documents": manifest, "no_case_study": sorted(no_case_study),
             "thin_readme": sorted(thin_readme), "projects": projects}, indent=1))
        oc = {k: sum(1 for x in props if x["outcome"] == k) for k in ("won", "replied", "ignored")}
        print(persona, "docs", len(manifest), "proposals", oc)


if __name__ == "__main__":
    main()
