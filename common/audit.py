"""Append-only audit log: user, server, tool, arguments, result, status, trace id (PII masked)."""
from __future__ import annotations

import json
import logging

from agent.guardrails import mask_obj

log = logging.getLogger("gigbid.audit")


def audit(server: str, tool: str, user_id: str | None, arguments: dict, result, status: str, trace_id: str | None) -> None:
    rec = {"user_id": user_id, "server": server, "tool": tool, "arguments": mask_obj(arguments),
           "result": mask_obj(result if isinstance(result, (dict, list)) else {"value": str(result)[:500]}),
           "status": status, "trace_id": trace_id}
    import os
    if not os.environ.get("DATABASE_URL"):
        from pathlib import Path
        f = Path(os.environ.get("GIGBID_AUDIT_FILE", "var/audit/audit.jsonl"))
        f.parent.mkdir(parents=True, exist_ok=True)
        with open(f, "a") as fh:  # append-only file when no database is configured (local eval runs)
            fh.write(json.dumps(rec, default=str) + "\n")
        return
    try:
        from common import db
        db.x("INSERT INTO audit_log(user_id, server, tool, arguments, result, status, trace_id) VALUES (%s,%s,%s,%s,%s,%s,%s)",
             (user_id, server, tool, json.dumps(rec["arguments"], default=str)[:20000],
              json.dumps(rec["result"], default=str)[:20000], status, trace_id))
    except Exception as e:  # noqa: BLE001 - audit must not take the tool down, but must be visible
        log.error("audit write failed (%s): %s", e, json.dumps(rec, default=str)[:500])
