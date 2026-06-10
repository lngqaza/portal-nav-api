# Stage 1: Export ONNX models — PyTorch only needed here, never in runtime
FROM python:3.12-slim AS model-builder

RUN apt-get update && apt-get install -y --no-install-recommends build-essential git curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "numpy==1.26.4" \
    "onnxscript" \
    "torch==2.3.1" \
    "sentence-transformers==3.4.1" \
    "optimum[onnxruntime]==1.27.0" \
    "onnxruntime==1.26.0" \
    "transformers==4.51.3"

RUN optimum-cli export onnx \
    --model sentence-transformers/all-MiniLM-L6-v2 \
    --task feature-extraction \
    /onnx_models/minilm

RUN optimum-cli export onnx \
    --model cross-encoder/ms-marco-MiniLM-L-6-v2 \
    --task text-classification \
    /onnx_models/reranker

# Stage 2: AWS Lambda Python 3.12 — official AWS base image
FROM public.ecr.aws/lambda/python:3.12

# Patch all OS packages to eliminate fixable CVEs in the base image.
# dnf update pulls the latest security patches from Amazon Linux repos.
RUN dnf update -y && dnf clean all

# ONNX models (kept separate from Python packages)
COPY --from=model-builder /onnx_models ${LAMBDA_TASK_ROOT}/onnx_models

# Runtime dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -t ${LAMBDA_TASK_ROOT}

# Application code
COPY handler.py  ${LAMBDA_TASK_ROOT}/
COPY core/       ${LAMBDA_TASK_ROOT}/core/
COPY models/     ${LAMBDA_TASK_ROOT}/models/
COPY services/   ${LAMBDA_TASK_ROOT}/services/
COPY routes/     ${LAMBDA_TASK_ROOT}/routes/

ENV EMBEDDING_MODEL_PATH=${LAMBDA_TASK_ROOT}/onnx_models/minilm/model.onnx
ENV RERANKER_MODEL_PATH=${LAMBDA_TASK_ROOT}/onnx_models/reranker/model.onnx
ENV PYTHONPATH=${LAMBDA_TASK_ROOT}

CMD ["handler.lambda_handler"]
