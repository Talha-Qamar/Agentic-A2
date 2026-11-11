# One image for every GigBid Python service (api, worker, gigsim, MCP servers). The command picks the role.
# --- web build ---
FROM node:20-slim AS web
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY apps/web/ ./
RUN npx vite build

# --- python runtime ---
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app FASTEMBED_CACHE_PATH=/models PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements-eval.txt ./
RUN pip install -r requirements-eval.txt && pip uninstall -y ruff pytest pytest-asyncio || true
# open embedding + reranker models baked into the image (CPU, ONNX)
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5'); \
from fastembed.rerank.cross_encoder import TextCrossEncoder; TextCrossEncoder('Xenova/ms-marco-MiniLM-L-6-v2')"
COPY . .
COPY --from=web /web/dist /app/apps/web/dist
# node runtime only for the third-party GitHub MCP server (stdio, `npx -y @modelcontextprotocol/server-github@2025.4.8`)
COPY --from=web /usr/local/bin/node /usr/local/bin/node
COPY --from=web /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
# pre-compute portfolio embeddings for the deployed retrieval variant
RUN python -m rag.warm || echo "warm skipped"
EXPOSE 8000
CMD ["sh", "-c", "uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
