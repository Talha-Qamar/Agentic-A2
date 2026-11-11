# ADR 0003: Retrieval pipeline chosen by measurement

**Decision.** Deploy **V9 skill graph** (requirement decomposition -> skills -> projects via a graph built from chunk
metadata, outcome boost, embedding tie-break, BM25+dense fallback when a requirement names no known skill).
**Evidence.** `evals/results/rag_benchmark.json` (600-job dev set, 247 BID jobs scored, bge-small-en-v1.5 embeddings):
V9 had the best Recall@5, MRR and nDCG@10 of the nine variants; cross-encoder reranking (V3) *reduced* quality and
added ~1.9 s p95. Ablations in `rag_ablation.json`.
**Caveat.** Gold evidence is defined through skills, which favours skill-based retrieval on explicitly named
requirements; recall on jobs with implied requirements is reported separately.
