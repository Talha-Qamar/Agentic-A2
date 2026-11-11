<!-- prompt: verifier_judge v1 | node: verifier | tier: small -->
Decide whether the EVIDENCE supports the CLAIM made by a freelancer about their own experience.
supported = the evidence states the same thing (numbers and names must match).
partial = the evidence supports the gist but not a specific detail in the claim.
unsupported = the evidence does not support it.
Return JSON {"verdict": "supported"|"partial"|"unsupported", "reason": str}.
