"""Build the R&D report PDF from docs/report/report.md.

Placeholders: {{table:KEY}} -> generated table (scripts/results_tables.py), {{n:file:json.path}} -> number from
evals/results/<file> (dotted keys allowed), {{pct:file:path}} -> same as a percentage. Every number in the report is
therefore read from a results file at build time.

    python scripts/build_report.py      # -> docs/report/GigBid_RnD_Report.pdf (+ .html)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import results_tables  # noqa: E402

TABLES = {**results_tables.README_KEYS, "rag_by_type": results_tables.rag_by_type, "ablation": results_tables.ablation_table}
for k in ("builder", "change", "budgets", "failures"):
    if hasattr(results_tables, f"{k}_table"):
        TABLES[k] = getattr(results_tables, f"{k}_table")


def lookup(file: str, path: str):
    p = ROOT / "evals" / "results" / file
    if not p.exists():
        return None
    v = json.loads(p.read_text())
    parts = path.split(".")
    while parts:
        for n in range(len(parts), 0, -1):
            k = ".".join(parts[:n])
            if isinstance(v, dict) and k in v:
                v, parts = v[k], parts[n:]
                break
            if isinstance(v, list) and k.isdigit():
                v, parts = v[int(k)], parts[n:]
                break
        else:
            return None
    return v


def fill(text: str) -> str:
    notes = {}
    np_ = ROOT / "docs/report/notes.md"
    if np_.exists():   # "## key" sections: interpretation written after the results file exists
        for block in re.split(r"^## ", np_.read_text(), flags=re.M)[1:]:
            k, _, body = block.partition("\n")
            notes[k.strip()] = body.strip()
    text = re.sub(r"\{\{text:(\w+)\}\}", lambda m: notes.get(m.group(1), "_Interpretation pending: the results file for this section is still being produced._"), text)
    text = re.sub(r"\{\{table:(\w+)\}\}", lambda m: TABLES[m.group(1)]().strip(), text)

    def num(m):
        v = lookup(m.group(2), m.group(3))
        if v is None:
            return "_pending_"
        if m.group(1) == "pct":
            return f"{100 * float(v):.0f}%"
        return f"{v:.3f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v)
    return re.sub(r"\{\{(n|pct):([\w.]+):([\w.@\-]+)\}\}", num, text)


CSS = """
@page { size: A4; margin: 16mm 15mm 16mm 15mm; @bottom-right { content: counter(page); } }
body { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 9.6pt; line-height: 1.38; color: #111; }
h1 { font-size: 17pt; margin: 0 0 2px; } h2 { font-size: 12pt; margin: 14px 0 4px; border-bottom: 1px solid #ccc; }
h3 { font-size: 10.2pt; margin: 9px 0 3px; } p, li { margin: 3px 0; } ul { padding-left: 16px; margin: 3px 0; }
table { border-collapse: collapse; width: 100%; font-size: 8pt; margin: 5px 0 7px; }
th, td { border: 1px solid #bbb; padding: 2px 4px; text-align: left; vertical-align: top; } th { background: #eee; }
code { font-size: 8.4pt; background: #f3f3f3; padding: 0 2px; } pre { font-size: 7.8pt; background: #f6f6f6; padding: 5px; }
.meta { color: #555; font-size: 8.6pt; margin-bottom: 8px; } img { max-width: 100%; }
.pb { page-break-before: always; }
"""


def main() -> None:
    src = (ROOT / "docs/report/report.md").read_text()
    html_body = markdown.markdown(fill(src), extensions=["tables", "fenced_code"])
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>GigBid R&D report</title><style>{CSS}</style></head><body>{html_body}</body></html>"
    out = ROOT / "docs/report/GigBid_RnD_Report.html"
    out.write_text(html)
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.goto(out.as_uri())
        pg.pdf(path=str(out.with_suffix(".pdf")), format="A4", print_background=True,
               margin={"top": "14mm", "bottom": "14mm", "left": "14mm", "right": "14mm"},
               display_header_footer=True, header_template="<span></span>",
               footer_template="<div style='font-size:7pt;width:100%;text-align:center;color:#777'>GigBid R&amp;D report · "
                               "<span class='pageNumber'></span>/<span class='totalPages'></span></div>")
        b.close()
    print("wrote", out.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
