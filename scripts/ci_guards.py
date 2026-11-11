"""CI guards: GigSim frozen (checksums), no inline prompts outside agent/prompts, every number tagged in README traces to
evals/results. Run: python scripts/ci_guards.py [--freeze]"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "gigsim" / "CHECKSUMS.sha256"


def gigsim_hashes() -> dict:
    files = sorted(p for p in (ROOT / "gigsim").rglob("*") if p.is_file() and p.suffix in (".py", ".yaml") and "__pycache__" not in str(p))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def check_gigsim() -> list[str]:
    if not FROZEN.exists():
        return ["gigsim/CHECKSUMS.sha256 missing (run with --freeze once)"]
    want = dict(line.split("  ")[::-1] for line in FROZEN.read_text().strip().splitlines())
    have = gigsim_hashes()
    return [f"GigSim file changed after freeze: {f}" for f in want if have.get(f) != want[f]]


PROMPT_RE = re.compile(r'"""?\s*(You are|Act as|Return ONLY|Return JSON)[^"]{40,}', re.S)


def check_prompts() -> list[str]:
    bad = []
    for p in (ROOT / "agent").rglob("*.py"):
        if p.name in ("stub_llm.py",):
            continue
        if re.search(r'(?m)^\s*(SYSTEM|PROMPT)_?[A-Z_]*\s*=\s*["\']{1,3}You are', p.read_text()):
            bad.append(f"inline prompt in {p.relative_to(ROOT)} (prompts live in agent/prompts/)")
    return bad


def check_readme_numbers() -> list[str]:
    """README numbers written as `<!--n:file:json.path-->value` must equal the value in evals/results/<file>."""
    readme = (ROOT / "README.md").read_text() if (ROOT / "README.md").exists() else ""
    bad = []
    for m in re.finditer(r"<!--n:([\w.]+):([\w.@\-]+)-->\s*([0-9.]+)", readme):
        f, path, shown = m.groups()
        try:
            v = json.loads((ROOT / "evals" / "results" / f).read_text())
            parts = path.split(".")
            while parts:  # keys may themselves contain dots (e.g. "check_at_previous_default_0.55")
                for n in range(len(parts), 0, -1):
                    if ".".join(parts[:n]) in v:
                        v, parts = v[".".join(parts[:n])], parts[n:]
                        break
                else:
                    raise KeyError(".".join(parts))
            if abs(float(v) - float(shown)) > 0.0051 * max(1, abs(float(v))):
                bad.append(f"README shows {shown} for {f}:{path} but results say {v}")
        except Exception as e:  # noqa: BLE001
            bad.append(f"README number {f}:{path} not traceable ({e})")
    return bad


def check_readme_tables() -> list[str]:
    """README tables between <!-- table:KEY --> markers must equal what scripts/results_tables.py generates."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import results_tables
    rp = ROOT / "README.md"
    if not rp.exists():
        return []
    cur = rp.read_text()
    return [] if results_tables.fill_readme(cur) == cur else ["README tables differ from evals/results (run scripts/results_tables.py --readme)"]


if __name__ == "__main__":
    if "--freeze" in sys.argv:
        FROZEN.write_text("\n".join(f"{h}  {f}" for f, h in gigsim_hashes().items()) + "\n")
        print(f"froze {len(gigsim_hashes())} GigSim files")
        sys.exit(0)
    problems = check_gigsim() + check_prompts() + check_readme_numbers() + check_readme_tables()
    for p in problems:
        print("GUARD FAILED:", p)
    sys.exit(1 if problems else 0)
