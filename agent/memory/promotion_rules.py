"""Memory promotion rules (C4). Nothing reaches long-term memory without passing one of these rules.

STYLE (from human edits of approved proposals)
  * every edit is diffed into candidate patterns (opening removed, phrase deleted, length change, sign-off, bullets);
  * a candidate is PROMOTED only if it was observed in >= memory.style.min_occurrences distinct edits within the
    user's last memory.style.window_edits edits, so a one-off tweak never becomes a rule;
  * at most memory.style.max_rules rules are kept (most-observed first); the user can delete any rule in the UI.

OUTCOMES (from marketplace events: replied / interview / hired / lost)
  * per job category, counts of submitted proposals and their outcomes are staged;
  * stats are PROMOTED once the category has >= memory.outcome.min_samples resolved proposals; the promoted item
    holds reply and win rates and the evidence items cited in proposals that got replies.

The execution trace is never written to memory.
"""
from __future__ import annotations

from agent import settings


def style_promotable(occurrences: int, edit_ids: list[int], recent_edit_ids: list[int]) -> bool:
    window = set(recent_edit_ids[-settings.get("memory.style.window_edits", 10):])
    distinct_recent = len(set(edit_ids) & window)
    return occurrences >= settings.get("memory.style.min_occurrences", 2) and distinct_recent >= settings.get("memory.style.min_occurrences", 2)


def outcome_promotable(resolved: int) -> bool:
    return resolved >= settings.get("memory.outcome.min_samples", 3)
