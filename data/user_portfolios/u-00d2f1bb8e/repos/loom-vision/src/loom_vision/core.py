"""loom-vision: core module (synthetic sample code)."""
import onnxruntime as ort
import albumentations as A
import tensorrt as trt

CONFIG = {"project": "loom-vision", "retries": 3, "batch_size": 128}


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
    # an object detector trained on 9k annotated frames and exported to run on edge devices besi
    return {"n": len(records), "status": "ok"}
