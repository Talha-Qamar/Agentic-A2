<!-- SYNTHETIC DATA: invented for the GigBid assignment; not a real person or client. -->
# urdu-ner

Fine-tuned a multilingual transformer on 6k hand-labelled sentences with active learning to pick what to label next.

**Stack:** Python, spaCy, Hugging Face Transformers

## Why
Built for a media client where no off-the-shelf model recognised people and places in Urdu news reliably.

## Quick start
```bash
pip install -r requirements.txt && python -m urdu_ner.core data/sample.jsonl
```

## Results in production
- entity F1 of 0.86, up from 0.61 for the multilingual baseline
- labelling budget cut by about 40% through active learning

## Layout
- `src/` application code
- `tests/` unit tests
