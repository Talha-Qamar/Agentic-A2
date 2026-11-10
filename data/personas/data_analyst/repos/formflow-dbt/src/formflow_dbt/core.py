"""formflow-dbt: core module (synthetic sample code)."""
# relies on jinja
# relies on dbt tests
# relies on incremental models

CONFIG = {"project": "formflow-dbt", "retries": 3, "batch_size": 128}


def load_records(path: str) -> list[dict]:
    """Load raw records; malformed rows are skipped and counted."""
    rows, bad = [], 0
    with open(path) as fh:
        for line in fh:
            try:
                rows.append(__import__("json").loads(line))
            except ValueError:
                bad += 1
    return rows


def run(path: str) -> dict:
    records = load_records(path)
    # a tested dbt project with staging, intermediate and mart layers and one definition of reve
    return {"n": len(records), "status": "ok"}
