# GigBid policy pack

The Compliance Guard (agent/nodes/compliance.py) enforces `rules.yaml` on every proposal and client message before it
reaches the human approval step. Severity `fix` rules are auto-fixed (offending sentence removed, logged in the
verdict); `block` rules stop the item with a stated reason.

| Rule | How it is checked |
|---|---|
| no_off_platform | regex for emails, phone numbers, messaging handles, off-platform payment words |
| no_external_links | URL regex; allowlist in `allowed_link_domains` |
| no_guarantees | guarantee / 100% / money-back patterns |
| no_fabrication | claim verification (rag/verify.py): unsupported claims are removed before the critic sees the draft |
| no_prompt_leak | system-prompt and envelope-tag markers |
| banned_phrases | `proposal.banned_phrases` in agent/config.yaml |
| fair_automation | architectural: marketplace write tools require a human-minted approval token |

Platform policy updates (GigSim `get_policy`) are also read at run time; required disclosures are added from
`disclosure.line` when `disclosure.required` is true.
