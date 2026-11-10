"""A general technology lexicon used to tag chunks with skills at ingestion time.

Hand-written and independent of the persona generator (it lists common tools, not
our personas' projects), so metadata extraction does not leak gold labels.
"""
TECH_TERMS = """
python javascript typescript go rust java kotlin swift php ruby c# c++ sql bash r scala
react next.js vue angular svelte react native expo flutter tailwind css html redux vite webpack storybook
node.js express nestjs fastapi django flask laravel rails spring graphql apollo trpc rest api websockets socket.io
postgresql postgres mysql mongodb redis sqlite elasticsearch opensearch supabase firebase prisma sqlalchemy dynamodb
snowflake bigquery redshift dbt airflow dagster prefect fivetran airbyte spark pyspark kafka flink
pandas numpy scipy scikit-learn sklearn statsmodels prophet xgboost lightgbm catboost pytorch torch tensorflow keras jax
transformers hugging face sentence-transformers spacy nltk langchain langgraph llamaindex openai anthropic ollama vllm
llm rag embeddings vector database pinecone qdrant weaviate faiss pgvector chroma milvus reranking cross-encoder
whisper yolo yolov8 opencv onnx onnxruntime tensorrt monai pydicom albumentations
mlflow wandb optuna shap lime evidently great expectations pydantic pytest jest playwright cypress selenium locust k6
docker kubernetes k8s helm terraform ansible aws gcp azure lambda ecs eks s3 cloudwatch vercel netlify render railway
github actions gitlab ci jenkins ci/cd prometheus grafana opentelemetry sentry datadog langsmith phoenix
celery rq dramatiq arq rabbitmq sqs pub/sub cron
stripe paypal shopify woocommerce wordpress sanity contentful strapi webflow
power bi tableau looker looker studio metabase superset excel google sheets vba power query dax mixpanel amplitude segment
google analytics ga4 bigquery geopandas qgis postgis shapely h3
auth oauth oidc saml sso webauthn passkeys jwt rbac row-level security
pwa service worker indexeddb workbox offline-first chrome extension manifest v3
a/b testing cohort analysis survival analysis forecasting time series classification regression clustering k-means
computer vision object detection ocr nlp named entity recognition speech-to-text summarization recommender systems
fraud detection churn prediction anomaly detection fine-tuning prompt engineering prompt injection guardrails agents
multi-agent tool calling evaluation llm-as-judge observability caching rate limiting idempotency webhooks
accessibility wcag aria seo lighthouse performance multi-tenancy microservices monorepo
""".split("\n")

TERMS: list[str] = sorted({t.strip() for line in TECH_TERMS for t in line.split("  ") for t in [t] if t.strip()}
                          | {w for line in TECH_TERMS for w in line.split() if w}, key=len, reverse=True)

# multi-word phrases kept together
PHRASES = ["react native", "next.js", "node.js", "hugging face", "sentence-transformers", "vector database",
           "github actions", "gitlab ci", "power bi", "power query", "looker studio", "google sheets", "google analytics",
           "row-level security", "service worker", "offline-first", "chrome extension", "manifest v3", "a/b testing",
           "cohort analysis", "survival analysis", "time series", "computer vision", "object detection",
           "named entity recognition", "speech-to-text", "recommender systems", "fraud detection", "churn prediction",
           "anomaly detection", "fine-tuning", "prompt engineering", "prompt injection", "multi-agent", "tool calling",
           "llm-as-judge", "rate limiting", "great expectations", "rest api", "pub/sub", "multi-tenancy", "k-means"]

IMPORT_TO_SKILL = {
    "sklearn": "scikit-learn", "torch": "pytorch", "pd": "pandas", "np": "numpy", "lgb": "lightgbm", "imblearn": "imbalanced-learn",
    "pgvector": "pgvector", "presidio_analyzer": "presidio", "pytorch_grad_cam": "grad-cam", "drf_spectacular": "drf-spectacular",
    "great_expectations": "great expectations", "pygeohash": "geohash", "prometheus_client": "prometheus",
    "@tanstack/react-query": "react-query", "@trpc/server": "trpc", "@casl/ability": "casl", "@simplewebauthn/server": "webauthn",
    "workbox-routing": "workbox", "expo-location": "expo", "graphql-tag": "graphql", "@jest/globals": "jest", "ai": "vercel ai sdk",
    "@storybook/react": "storybook", "k6/http": "k6", "mapbox-gl": "mapbox", "channels": "django channels",
}
