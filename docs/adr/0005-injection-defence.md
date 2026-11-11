# ADR 0005: Layered prompt-injection defence

Untrusted text (job posts, client messages) is (1) wrapped in a random-nonce envelope with an instruction hierarchy,
(2) scanned by a pattern detector (optionally Llama Prompt Guard 2) with offending sentences quarantined before the
writer sees them, (3) blocked at the output by the Compliance Guard (contact details, links, guarantees, prompt
leakage) and the claim verifier, and (4) unable to change the bid decision, which is a rule over evidence scores.
Attack success rates with defences off/on: `evals/results/injection_eval.json`.
