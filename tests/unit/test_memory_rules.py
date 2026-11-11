from agent.memory.promotion_rules import outcome_promotable, style_promotable
from agent.memory.style import extract_candidates


def test_one_off_edit_is_not_promoted():
    assert not style_promotable(1, [10], [8, 9, 10])
    assert style_promotable(2, [9, 10], [8, 9, 10])
    assert not style_promotable(2, [1, 2], list(range(3, 15)))  # old occurrences outside the window


def test_edit_diff_candidates():
    before = ("I hope you are well! I am a passionate developer with many years of experience in many technologies and industries. "
              "At Acme I cut costs 40% by rebuilding their reporting stack over six weeks with careful testing. "
              "I would love to help you with this project and deliver great results. Looking forward to hearing from you.")
    after = "At Acme I cut costs 40%.\n\n- week 1: audit\n- week 2: fix\n\nHappy to do a short call."
    keys = {c["key"] for c in extract_candidates(before, after)}
    assert "opening:direct" in keys and "format:bullets" in keys and "length:shorter" in keys


def test_outcome_needs_samples():
    assert not outcome_promotable(2) and outcome_promotable(3)
