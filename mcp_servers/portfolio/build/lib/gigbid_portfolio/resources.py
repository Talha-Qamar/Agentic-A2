"""Resource templates so a host can load full portfolio items."""
from __future__ import annotations

import json


def register(mcp, backend) -> None:
    @mcp.resource("portfolio://case/{case_id}", mime_type="text/markdown", title="Case study")
    def case(case_id: str) -> str:
        c = backend.get_case(case_id)
        if not c:
            raise ValueError(f"case study {case_id} not found")
        return f"# {c.get('title') or case_id}\n\n{c['text']}"

    @mcp.resource("portfolio://proposal/{proposal_id}", mime_type="application/json", title="Past proposal with outcome")
    def proposal(proposal_id: str) -> str:
        p = backend.get_proposal(proposal_id)
        if not p:
            raise ValueError(f"proposal {proposal_id} not found")
        return json.dumps(p, indent=1)

    @mcp.resource("portfolio://repo/{name}", mime_type="application/json", title="Repository files")
    def repo(name: str) -> str:
        r = backend.get_repo(name)
        if not r:
            raise ValueError(f"repo {name} not found")
        return json.dumps(r, indent=1)

    @mcp.resource("portfolio://profile", mime_type="application/json", title="Freelancer profile")
    def profile() -> str:
        return json.dumps(backend.profile(), indent=1)
