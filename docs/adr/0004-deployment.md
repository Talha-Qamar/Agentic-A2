# ADR 0004: Single-process deployment on Render's free tier

**Context.** Hugging Face Docker Spaces became paid; the budget is zero; the app must stay reachable until grading.
**Decision.** Render free web service running GigBid in all-in-one mode (GigSim, three MCP servers mounted as ASGI
apps, Arq worker as a background task) with Render free Postgres (pgvector) and Key Value. Open models via Groq.
Docker Compose remains the reference multi-service topology.
**Consequences.** 512 MB RAM and 0.1 CPU: embeddings are precomputed at build time and persisted to pgvector; the
instance sleeps after 15 minutes (cold start ~1 min); GigSim state resets on restart (accounts are re-provisioned).
