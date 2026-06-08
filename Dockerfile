# Stage 1: Build — export ONNX models, install runtime deps
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git \
    && rm -rf /var/lib/apt/lists/*

# Install model export toolchain globally (build-time only, not copied to runtime)
RUN pip install --no-cache-dir \
    "numpy==1.26.4" \
    "onnxscript" \
    "torch==2.3.1" \
    "sentence-transformers==3.0.1" \
    "optimum[onnxruntime]==1.21.2" \
    "onnxruntime==1.18.1" \
    "transformers==4.42.4"

# Export all-MiniLM-L6-v2 (embedding model) to ONNX via optimum-cli
RUN optimum-cli export onnx \
    --model sentence-transformers/all-MiniLM-L6-v2 \
    --task feature-extraction \
    /models/minilm

# Export cross-encoder (re-ranker) to ONNX via optimum-cli
RUN optimum-cli export onnx \
    --model cross-encoder/ms-marco-MiniLM-L-6-v2 \
    --task text-classification \
    /models/reranker

# Install runtime dependencies to /install prefix (copied to stage 2)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install "numpy==1.26.4"
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime — lean image, no build tools, no PyTorch
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
