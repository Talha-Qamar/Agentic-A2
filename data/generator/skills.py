"""Canonical skill vocabulary for the synthetic corpus and job generator.

``canon(s)`` maps any surface form to a canonical key.  ``IMPLIED`` gives
phrasings a client might use *without naming the skill* ("a task queue for
long-running jobs" instead of "Celery").  ``PROSE_SYNONYMS`` is used when the
same project is rendered in different documents so vocabulary drifts the way
it does in real portfolios.
"""
from __future__ import annotations

import re

ALIASES = {
    "postgresql": ["postgres", "pg", "postgresql", "postgre"],
    "javascript": ["js", "javascript"],
    "typescript": ["ts", "typescript"],
    "next.js": ["nextjs", "next.js", "next"],
    "node.js": ["node", "nodejs", "node.js"],
    "react native": ["react native", "react-native"],
    "scikit-learn": ["sklearn", "scikit-learn", "scikit learn"],
    "hugging face transformers": ["transformers", "hugging face transformers", "huggingface"],
    "pytorch": ["pytorch", "torch"],
    "authentication": ["auth", "authentication"],
    "audit logging": ["audit log", "audit logging", "audit trail"],
    "mobile app": ["mobile", "mobile app"],
    "jinja2": ["jinja", "jinja2"],
    "github actions": ["github actions", "gh actions"],
    "google analytics 4": ["ga4", "google analytics 4", "google analytics"],
    "power query": ["power query", "m language"],
    "dax": ["dax"],
    "llm-as-judge": ["llm-as-judge", "llm judge"],
    "openai api": ["openai api", "openai", "gpt-4", "chatgpt api"],
    "aws ecs": ["aws ecs", "ecs"],
    "redis pub/sub": ["redis pub/sub"],
    "abc analysis": ["abc analysis"],
    "rag": ["rag", "retrieval-augmented generation", "retrieval augmented generation"],
    "ci/cd": ["ci/cd", "cicd", "continuous deployment"],
    "row-level security": ["row-level security", "rls"],
    "a/b testing": ["a/b testing", "ab testing", "split testing", "experimentation"],
}

_ALIAS_INDEX = {}
for key, forms in ALIASES.items():
    for f in forms:
        _ALIAS_INDEX[f.lower()] = key


def canon(skill: str) -> str:
    s = re.sub(r"\s+", " ", skill.strip().lower())
    return _ALIAS_INDEX.get(s, s)


# Phrases a client may use instead of naming the skill.  Keys are canonical.
IMPLIED = {
    "celery": ["a task queue so long-running jobs run in the background", "background workers so the API never blocks"],
    "background jobs": ["work that runs asynchronously after the user clicks submit"],
    "redis": ["an in-memory cache in front of the database"],
    "langgraph": ["a stateful agent workflow with branching steps and a human review step"],
    "multi-agent": ["several cooperating AI agents, for example a planner and a reviewer"],
    "critique loop": ["a self-review step where the AI checks and revises its own draft"],
    "agents": ["an AI assistant that can take actions through our APIs, not just chat"],
    "tool calling": ["the model needs to call our internal APIs to look things up"],
    "rag": ["answers grounded in our own documents, with sources", "a chatbot that only answers from our knowledge base"],
    "citations": ["every answer must point to the paragraph it came from"],
    "semantic search": ["search that understands meaning, not just keywords"],
    "hybrid search": ["search that handles both exact product codes and natural-language queries"],
    "reranking": ["better ordering of search results so the best hit is first"],
    "embeddings": ["vector representations of our text"],
    "qdrant": ["a vector database"], "pinecone": ["a managed vector database"], "pgvector": ["vector search inside Postgres"],
    "faiss": ["fast nearest-neighbour search"],
    "fastapi": ["a Python web API"],
    "docker": ["containerised deployment"],
    "airflow": ["scheduled pipelines that run every night"],
    "pytorch": ["deep learning model training"],
    "fine-tuning": ["adapting a pre-trained model to our own labelled data"],
    "forecasting": ["predicting next month's demand per product"],
    "time series": ["data that changes week by week and has seasonality"],
    "computer vision": ["analysing images from our cameras"],
    "object detection": ["finding and boxing defects in camera frames"],
    "edge deployment": ["running the model on a small device on site without the cloud"],
    "ocr": ["reading text from scanned documents"],
    "document ai": ["pulling structured fields out of PDFs and scans"],
    "information extraction": ["turning free-text documents into structured JSON"],
    "named entity recognition": ["pulling out names of people, places and organisations from articles"],
    "speech-to-text": ["transcribing voice recordings"], "whisper": ["automatic transcription of audio files"],
    "summarization": ["short summaries of long text"],
    "recommender systems": ["personalised suggestions for each user"],
    "collaborative filtering": ["recommendations based on what similar users liked"],
    "fraud detection": ["flagging suspicious transactions before they are approved"],
    "imbalanced classification": ["very few positive examples compared to negatives"],
    "explainability": ["a clear reason for every model decision"], "shap": ["feature-level explanations for each prediction"],
    "mlops": ["reliable retraining and deployment of models"], "mlflow": ["experiment tracking and a model registry"],
    "llm evaluation": ["a way to measure whether our AI outputs are getting better or worse"],
    "prompt engineering": ["better prompts for our assistant"],
    "prompt injection": ["make sure the chatbot cannot be manipulated by text hidden in user inputs"],
    "guardrails": ["safety checks on what the AI is allowed to say and do"],
    "pii redaction": ["hiding personal data like emails and phone numbers in logs"],
    "llm serving": ["hosting an open-source language model ourselves"], "vllm": ["fast self-hosted LLM inference"],
    "model routing": ["sending easy requests to a cheaper model"],
    "observability": ["tracing and dashboards for every model call"],
    "churn prediction": ["predicting which customers will cancel"],
    "classification": ["sorting items into categories automatically"],
    "nlp": ["working with free text in several languages"],
    "data labelling": ["getting our images labelled efficiently"], "active learning": ["choosing which examples to label next"],
    "medical imaging": ["analysing X-ray or scan images"],
    "stripe": ["online card payments"], "payments": ["taking payments online"],
    "subscriptions": ["recurring monthly billing with plan upgrades"], "webhooks": ["reacting to events sent by a third-party service"],
    "websockets": ["live updates pushed to the browser without refreshing"], "real-time": ["live tracking on a map"],
    "next.js": ["a fast, SEO-friendly React website"], "react": ["a modern single-page frontend"],
    "react native": ["one app for both iOS and Android"], "mobile app": ["an app on the App Store and Google Play"],
    "multi-tenancy": ["each customer company must only ever see its own data"],
    "rbac": ["different permissions for admins, managers and staff"], "role-based access": ["admins and staff need different access levels"],
    "pwa": ["an installable web app"], "offline-first": ["it must keep working without internet and sync later"],
    "accessibility": ["usable with screen readers and keyboard only"], "wcag": ["we need to pass an accessibility audit"],
    "ci/cd": ["automated tests and deployment on every push"], "github actions": ["a build pipeline in our GitHub repo"],
    "terraform": ["cloud infrastructure defined as code"], "devops": ["help with servers and deployments"],
    "graphql": ["one flexible API so the mobile app stops making a dozen calls per screen"],
    "sso": ["enterprise single sign-on for our customers"], "passkeys": ["passwordless login"],
    "authentication": ["secure login and sessions"],
    "shopify storefront api": ["our Shopify store, rebuilt to be much faster"], "headless commerce": ["a custom storefront on top of our existing commerce backend"],
    "cms": ["non-technical staff must be able to edit content"], "sanity": ["a headless CMS"],
    "performance": ["our site is slow and we are losing customers"], "query optimisation": ["database queries that take seconds"],
    "chrome extensions": ["a browser add-on for our sales team"], "browser extension": ["a small tool that lives in the browser"],
    "django": ["a Python backend with an admin panel"], "laravel": ["our existing PHP application"],
    "dashboards": ["one screen where managers can see the key numbers"], "data visualization": ["clear charts of our data"],
    "rest api": ["a clean API for our mobile and web clients"], "marketplace": ["a two-sided platform connecting customers and providers"],
    "dbt": ["tested, version-controlled SQL transformations"], "snowflake": ["a cloud data warehouse"], "bigquery": ["Google's data warehouse"],
    "power bi": ["an interactive Microsoft dashboard for managers"], "tableau": ["interactive visual reports for leadership"],
    "looker studio": ["a free dashboard connected to our Google data"], "excel": ["better spreadsheets"], "vba": ["automating repetitive spreadsheet work with macros"],
    "financial modeling": ["a forecast P&L, balance sheet and cash flow model"], "fp&a": ["monthly budgeting and variance reporting"],
    "cohort analysis": ["how retention differs by signup month"], "churn analysis": ["understanding why customers cancel"],
    "a/b testing": ["analysing our experiments properly before we ship changes"], "statistics": ["sound statistical analysis"],
    "attribution": ["which marketing channels actually drive sales"], "google analytics 4": ["our website analytics data"],
    "geospatial": ["map-based analysis of locations"], "site selection": ["choosing where to open the next branch"],
    "survey analysis": ["analysing results from a large customer survey"], "segmentation": ["grouping customers into actionable segments"],
    "product analytics": ["seeing where users drop off in our app"], "event tracking": ["tracking what users click in our product"],
    "elasticity": ["how price changes affect demand"], "pricing analytics": ["deciding discount levels with data"],
    "data warehouse": ["moving our spreadsheets into a proper central database"], "data pipelines": ["automated data flows from our tools"],
    "data quality": ["catching bad data before it reaches reports"], "kpis": ["the handful of numbers that matter for the business"],
    "sql": ["writing queries against our database"], "pandas": ["cleaning data in Python"],
    "data modeling": ["a clean model of our sales data"], "risk analytics": ["monitoring loan portfolio risk"],
    "people analytics": ["understanding why employees leave"], "reporting automation": ["reports that send themselves every week"],
    "inventory analytics": ["finding dead stock and late suppliers"], "market research": ["insights from consumer research data"],
}

# How the *same* skill is written in different documents (case study / README / CV).
PROSE_SYNONYMS = {
    "postgresql": ["PostgreSQL", "Postgres", "pg"],
    "next.js": ["Next.js", "Next", "NextJS"],
    "node.js": ["Node.js", "Node", "NodeJS"],
    "typescript": ["TypeScript", "TS", "typed JavaScript"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit-learn"],
    "pytorch": ["PyTorch", "torch", "PyTorch"],
    "openai api": ["the OpenAI API", "GPT-4-class models", "OpenAI"],
    "aws": ["AWS", "Amazon Web Services", "AWS"],
    "power bi": ["Power BI", "PBI", "Power BI"],
    "google analytics 4": ["Google Analytics 4", "GA4", "GA4"],
    "fastapi": ["FastAPI", "a FastAPI service", "FastAPI"],
    "docker": ["Docker", "containers", "Docker"],
    "redis": ["Redis", "an in-memory cache", "Redis"],
    "excel": ["Excel", "spreadsheets", "MS Excel"],
}

# Skills each persona does NOT have, used to create low-fit jobs.
OFF_DOMAIN = {
    "ai_ml_engineer": ["Unity", "WordPress themes", "Figma", "Solidity", "Salesforce Apex", "SAP ABAP", "Swift",
                        "video editing", "SEO", "Shopify Liquid", "Flutter", "Adobe Illustrator"],
    "fullstack_web_dev": ["Solidity", "Unity", "SAP ABAP", "Kubernetes operators", "Rust", "Swift", "PyTorch",
                          "Tableau", "Salesforce Apex", "video editing", "3D modeling", "COBOL"],
    "data_analyst": ["React", "Kubernetes", "Unity", "Swift", "Figma", "Solidity", "Flutter", "Next.js",
                     "Salesforce Apex", "video editing", "PyTorch", "embedded C"],
}


def prose(skill: str, variant: int) -> str:
    """Render a skill name in one of three document voices."""
    c = canon(skill)
    if c in PROSE_SYNONYMS:
        opts = PROSE_SYNONYMS[c]
        return opts[variant % len(opts)]
    return skill
