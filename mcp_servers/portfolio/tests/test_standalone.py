"""The published Portfolio server works standalone on any portfolio folder (no GigBid code needed at runtime)."""
import asyncio
from pathlib import Path

from mcp_servers.portfolio.backend import StandaloneBackend
from mcp_servers.portfolio.server import build_server

DEMO = Path(__file__).resolve().parents[3] / "data" / "personas" / "fullstack_web_dev"


def test_standalone_search_and_case_study():
    b = StandaloneBackend(DEMO)
    hits = b.search("Stripe subscriptions billing webhooks", 3, None)
    assert hits and any("stripe" in h["text"].lower() for h in hits)
    case = next(i for i in b.items if i.type == "case_study")
    assert b.get_case(case.id)["text"]


def test_server_lists_tools_resources_prompts():
    m = build_server(StandaloneBackend(DEMO))
    assert {t.name for t in asyncio.run(m.list_tools())} >= {"search_evidence", "get_case_study", "list_skills"}
    assert len(asyncio.run(m.list_prompts())) >= 3
    assert asyncio.run(m.list_resource_templates())
