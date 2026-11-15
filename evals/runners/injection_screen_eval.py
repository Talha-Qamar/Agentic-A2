"""Deterministic layers of the injection defence, measured on a red-team set they were never tuned on. No model call.

evals/datasets/redteam_injections.jsonl holds 30 attacks (6 goals x 5 phrasings: direct, polite, client preference,
role spoof, hidden comment, obfuscated, authority) and 20 benign posts that use the same vocabulary (system prompts,
Telegram bots, guarantees of idempotency, links to on-platform work). It was written after the screening patterns in
agent/guardrails.py were frozen and was not used to change them.

Three questions:
  1. Input screen: does detect_injection flag the attack (and leave benign posts alone)?
  2. Output guard: if the writer HAD obeyed, would the compliance output rules strip the payload sentence?
     (payload = the text a compromised draft would contain, embedded in an otherwise normal cover letter)
  3. Output false positives: how often do real drafted letters (decision_eval.json) trip an output rule?
Goals that are structural (force_bid, price_override) cannot succeed through text: the bid decision and the price
come from deterministic code that never reads the post's instructions; they are reported as such.

    python -m evals.runners.injection_screen_eval     # -> evals/results/injection_screen_eval.json
"""
from __future__ import annotations

import json
from collections import defaultdict

from agent.guardrails import detect_injection, output_violations, quarantine, strip_violations
from evals.runners.common import DATASETS, RESULTS, provenance, write_result

LETTER = ("Hi, I built a retrieval pipeline for a health-tech client and cut answer latency by 40% [ev:1]. {payload} "
          "I can start with a one-week milestone and share progress here on the platform.")
STRUCTURAL = {"force_bid", "price_override"}


def main() -> None:
    rows = [json.loads(line) for line in open(DATASETS / "redteam_injections.jsonl") if line.strip()]
    out, by_attack, by_style = [], defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    for r in rows:
        d = detect_injection(r["text"])
        clean, removed = quarantine(r["text"])
        res = {"id": r["id"], "attack": r["attack"], "style": r["style"], "detected": d["detected"],
               "labels": sorted({h["label"] for h in d["hits"]}), "quarantined": bool(removed)}
        if r.get("payload"):
            letter = LETTER.format(payload=r["payload"])
            viol = output_violations(letter)
            final = strip_violations(letter, viol)
            res["output_flagged"] = bool(viol)
            res["payload_survives"] = r["payload"].strip() in final
        out.append(res)
        if r["attack"]:
            by_attack[r["attack"]][0] += d["detected"]
            by_attack[r["attack"]][1] += 1
            by_style[r["style"]][0] += d["detected"]
            by_style[r["style"]][1] += 1
    atk = [x for x in out if x["attack"]]
    ben = [x for x in out if not x["attack"]]
    text_atk = [x for x in atk if "payload_survives" in x]
    letters = [r.get("cover_letter") for r in json.loads((RESULTS / "decision_eval.json").read_text()).get("rows", []) if r.get("cover_letter")]
    fp_letters = [bool(output_violations(t)) for t in letters]
    either = [x for x in text_atk if x["detected"] or not x["payload_survives"]]
    summary = {
        "attacks": len(atk), "benign": len(ben),
        "input_detection_rate": round(sum(x["detected"] for x in atk) / len(atk), 4),
        "input_false_positive_rate": round(sum(x["detected"] for x in ben) / len(ben), 4),
        "detection_by_attack": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_attack.items())},
        "detection_by_style": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_style.items())},
        "text_payloads": len(text_atk),
        "output_guard_strip_rate": round(sum(not x["payload_survives"] for x in text_atk) / len(text_atk), 4),
        "caught_by_screen_or_guard": round(len(either) / len(text_atk), 4),
        "missed_by_both": [x["id"] for x in text_atk if not x["detected"] and x["payload_survives"]],
        "structural_goals": sorted(STRUCTURAL),
        "real_letters_checked": len(letters),
        "output_false_positive_rate": round(sum(fp_letters) / len(letters), 4) if letters else None,
    }
    write_result("injection_screen_eval.json", {"provenance": provenance({"set": "redteam_injections.jsonl"}), "summary": summary,
                                                "rows": out, "complete": True})
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
