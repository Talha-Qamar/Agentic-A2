"""formflow-infra: core module (synthetic sample code)."""
# relies on ecs
# relies on cloudwatch
# relies on blue-green deploys

CONFIG = {"project": "formflow-infra", "retries": 3, "batch_size": 32}


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
    # containerised the app, wrote Terraform for the AWS stack and a GitHub Actions pipeline wit
    return {"n": len(records), "status": "ok"}
