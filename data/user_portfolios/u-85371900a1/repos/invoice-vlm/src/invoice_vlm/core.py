"""invoice-vlm: core module (synthetic sample code)."""
from transformers import AutoProcessor, VisionEncoderDecoderModel
from pdf2image import convert_from_path
from pydantic import BaseModel, Field

CONFIG = {"project": "invoice-vlm", "retries": 3, "batch_size": 128}


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
    # a fine-tuned document-understanding model that outputs JSON line items, validated against 
    return {"n": len(records), "status": "ok"}
