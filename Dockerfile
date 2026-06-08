# Stage 1: Build — download models, install deps
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install sentence-transformers optimum[onnxruntime] onnxruntime transformers
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Export all-MiniLM-L6-v2 to ONNX
RUN PYTHONPATH=/install/lib/python3.12/site-packages python -c "\
from optimum.onnxruntime import ORTModelForFeatureExtraction; \
from transformers import AutoTokenizer; \
m = ORTModelForFeatureExtraction.from_pretrained('sentence-transformers/all-MiniLM-L6-v2', export=True); \
m.save_pretrained('/models/minilm'); \
AutoTokenizer.from_pretrained('sentence-transformers/all-MiniLM-L6-v2').save_pretrained('/models/minilm')"

# Export cross-encoder to ONNX
RUN PYTHONPATH=/install/lib/python3.12/site-packages python -c "\
from optimum.onnxruntime import ORTModelForSequenceClassification; \
from transformers import AutoTokenizer; \
m = ORTModelForSequenceClassification.from_pretrained('cross-encoder/ms-marco-MiniLM-L-6-v2', export=True); \
m.save_pretrained('/models/reranker'); \
AutoTokenizer.from_pretrained('cross-encoder/ms-marco-MiniLM-L-6-v2').save_pretrained('/models/reranker')"

# Stage 2: Runtime
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local
COPY --from=builder /models /app/models

WORKDIR /app
COPY app/ ./app/
COPY migrations/ ./migrations/
COPY alembic.ini .

RUN groupadd -r appuser && useradd -r -g appuser -u 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

ENV EMBEDDING_MODEL_PATH=/app/models/minilm/model.onnx
ENV RERANKER_MODEL_PATH=/app/models/reranker/model.onnx
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
