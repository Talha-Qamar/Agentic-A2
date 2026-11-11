---
repo: clause-rag
source: local-checkout (GitHub MCP unavailable: ExceptionGroup)
builder: x3-portfolio-builder
generated: 2026-11-11
verified_claims: 2
removed_unsupported: 0
skills: [pydantic, pytest, fastapi, langgraph, qdrant, asyncio]
---
# Case study: clause-rag

Situation: A retrieval pipeline that chunks contracts by clause heading, retrieves with hybrid search and forces every answer to quote the clause it relies on.

Task: build and ship clause-rag.

Action: I implemented it with pydantic, pytest, fastapi, langgraph, qdrant, asyncio (see requirements.txt, src/clause_rag/core.py, tests/test_core.py).

Result: Built for a legal client where lawyers spent hours locating indemnity and termination clauses across 300-page vendor contracts.