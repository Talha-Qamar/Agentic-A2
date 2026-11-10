"""Platform policy versions. The active version is chosen by env or admin call."""
from __future__ import annotations

import math
import os
import re
from functools import lru_cache
from pathlib import Path

import yaml

POLICY_DIR = Path(__file__).parent / "policies"
DEFAULT_VERSION = "2026-10-27"


@lru_cache(maxsize=8)
def load_policy(version: str) -> dict:
    return yaml.safe_load((POLICY_DIR / f"{version}.yaml").read_text())


def available_versions() -> list[str]:
    return sorted(p.stem for p in POLICY_DIR.glob("*.yaml"))


def current_policy(store) -> dict:
    version = store.meta("policy_version") or os.environ.get("GIGSIM_POLICY_VERSION", DEFAULT_VERSION)
    return load_policy(version)


def connects_cost(policy: dict, job: dict) -> int:
    c = policy["connects"]
    if job.get("budget_type") == "hourly" or job.get("is_hourly"):
        return int(c["hourly_cost"])
    budget = float(job.get("budget_max") or job.get("budget") or 0)
    if "formula" in c:
        f = c["formula"]
        return int(min(f["cap"], f["base"] + math.ceil(budget / f["per_usd"])))
    for tier in c["fixed_tiers"]:
        if tier["max_budget"] is None or budget <= tier["max_budget"]:
            return int(tier["cost"])
    return int(c["fixed_tiers"][-1]["cost"])


CONTACT_RE = re.compile(
    r"([\w.+-]+@[\w-]+\.[\w.]+)|(\+?\d[\d\s().-]{8,}\d)|(whats\s?app|telegram|skype|signal)\b|(t\.me/|wa\.me/)", re.I)


def policy_violations(policy: dict, text: str) -> list[str]:
    """Checks GigSim itself enforces at submission time (a subset of the policy)."""
    v = []
    if CONTACT_RE.search(text):
        v.append("no_off_platform")
    if policy["requirements"].get("ai_disclosure"):
        if not re.search(policy["requirements"]["ai_disclosure_pattern"], text):
            v.append("ai_disclosure")
    lim = policy["limits"]
    if len(text) > lim["max_cover_letter_chars"]:
        v.append("too_long")
    if len(text) < lim["min_cover_letter_chars"]:
        v.append("too_short")
    return v
