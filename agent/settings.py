"""Load agent/config.yaml with ${ENV:-default} expansion. Single source of configuration."""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(os.environ.get("GIGBID_CONFIG", ROOT / "agent" / "config.yaml"))
_VAR = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")


def _expand(v: Any) -> Any:
    if isinstance(v, str):
        def rep(m):
            return os.environ.get(m.group(1), m.group(2) if m.group(2) is not None else "")
        out = _VAR.sub(rep, v)
        if _VAR.search(v):
            if out.lower() in ("true", "false"):
                return out.lower() == "true"
            if re.fullmatch(r"-?\d+(\.\d+)?", out):
                return float(out) if "." in out else int(out)
        return out
    if isinstance(v, dict):
        return {k: _expand(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_expand(x) for x in v]
    return v


@lru_cache(maxsize=1)
def cfg() -> dict:
    return _expand(yaml.safe_load(CONFIG_PATH.read_text()))


def reload() -> dict:
    cfg.cache_clear()
    return cfg()


def get(path: str, default: Any = None) -> Any:
    cur: Any = cfg()
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def model_for(node: str, fallback: bool = False, profile: str | None = None) -> dict:
    c = cfg()
    prof = profile or os.environ.get("GIGBID_PROFILE") or c["profile"]
    tier = c["nodes"].get(node, "small")
    key = f"fallback_{tier}" if fallback else tier
    spec = c["profiles"][prof][key]
    spec = dict(spec[0] if isinstance(spec, list) else spec)
    spec["profile"] = prof
    spec["tier"] = tier
    return spec


def model_candidates(node: str, profile: str | None = None) -> list[dict]:
    """Primary model for the node, then its fallbacks in order (a fallback entry may be a single spec or a list)."""
    c = cfg()
    prof = profile or os.environ.get("GIGBID_PROFILE") or c["profile"]
    tier = c["nodes"].get(node, "small")
    p = c["profiles"][prof]
    fb = p.get(f"fallback_{tier}") or []
    out = []
    for i, spec in enumerate([p[tier]] + (fb if isinstance(fb, list) else [fb])):
        out.append(dict(spec, profile=prof, tier=tier, fallback=i > 0))
    return out


def price(model: str) -> dict:
    table = cfg()["pricing_usd_per_mtok"]
    return table.get(model, table["default"])


def policy_rules() -> dict:
    return yaml.safe_load((ROOT / cfg()["policy_pack"]).read_text())
