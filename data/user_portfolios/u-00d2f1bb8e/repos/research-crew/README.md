<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# research-crew

Planner, researcher and critic agents with a bounded revision loop and source links on every paragraph.

**Stack:** Python, LangGraph, Tavily API, Pinecone, Streamlit

## Why
Built for a finance client where first drafts of company notes took analysts most of a day.

## Quick start
```bash
pip install -r requirements.txt && python -m research_crew.core data/sample.jsonl
```

## Results in production
- draft time cut from about 6 hours to 35 minutes
- analysts kept 70% of generated paragraphs

## Layout
- `src/` application code
- `tests/` unit tests
