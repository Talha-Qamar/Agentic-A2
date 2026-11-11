# Changelog

## 2026-11-02 platform policy update (GigSim policy `2026-11-02`)
GigSim released a policy update: Connects cost now scales with budget (2 + ceil(budget/250), cap 16; hourly 10),
proposals drafted with automation tools must carry an AI-assistance disclosure, and each account may submit at most
5 proposals per rolling 24 hours.

How GigBid absorbed it - see the commit tagged `change-request-2026-11-02`:
* `data/policy_pack/rules.yaml`: `disclosure.required: true`, disclosure line, new `ai_disclosure` rule;
* `agent/config.yaml`: policy version note; no code changes were needed for Connects pricing (read live from
  `get_policy`/dry-run) or the daily cap (GigSim returns `daily_proposal_cap`, surfaced as `needs_attention`).
Measured effort and before/after results are in the report (section "Change request").
