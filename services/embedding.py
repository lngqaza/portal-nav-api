"""L1: ONNX sentence-transformer — encode + cosine search against nav_index."""
import logging
import os
import threading
from typing import List, Optional

import numpy as np

from core.config import settings
from core.db import get_conn
from models.navigation import EmbeddingResult

logger = logging.getLogger(__name__)

_session = None
_tokenizer = None
# ONNX InferenceSession is NOT thread-safe for concurrent run() calls.
# All encode() calls acquire this lock so Lambda's ThreadPoolExecutor
# (used by handle_batch) cannot corrupt the session state.
_lock = threading.Lock()


def load_model():
    global _session, _tokenizer
    path = settings.EMBEDDING_MODEL_PATH
    if not os.path.exists(path):
        logger.warning("Embedding model not found at %s — L1 disabled", path)
        return
    try:
        import onnxruntime as ort
        from transformers import AutoTokenizer
        _session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        _tokenizer = AutoTokenizer.from_pretrained(os.path.dirname(path))
        logger.info("Embedding model loaded from %s", path)
    except Exception as e:
        logger.error("Embedding model load failed: %s", e)


def encode(text: str) -> Optional[np.ndarray]:
    if not _session or not _tokenizer:
        return None
    try:
        enc = _tokenizer(text, padding=True, truncation=True, max_length=128, return_tensors="np")
        valid_inputs = {inp.name for inp in _session.get_inputs()}
        model_inputs = {k: v for k, v in enc.items() if k in valid_inputs}
        with _lock:
            out = _session.run(None, model_inputs)
        mask = enc["attention_mask"][:, :, None].astype(np.float32)
        emb = (out[0] * mask).sum(1) / mask.sum(1).clip(min=1e-9)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        return (emb / norms)[0].astype(np.float32)
    except Exception as e:
        logger.error("encode error: %s", e)
        return None


def search(query: str, top_k: int = 10, scope: list = None) -> List[EmbeddingResult]:
    """Cosine search across the key's site scope. Results from sites other
    than the home site (scope[0]) are penalised by CROSS_SITE_PENALTY so
    shared content is findable but the home site's pages win ties."""
    scope = scope or ["default"]
    vec = encode(query)
    if vec is None:
        return []
    vec_str = "[" + ",".join(f"{v:.6f}" for v in vec.tolist()) + "]"
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT path, label, description,
                           (1 - (embedding <=> %s::vector))
                             * CASE WHEN site_id = %s THEN 1.0 ELSE %s END AS score
                    FROM nav_index
                    WHERE embedding IS NOT NULL AND site_id = ANY(%s)
                    ORDER BY score DESC
                    LIMIT %s
                    """,
                    (vec_str, scope[0], settings.CROSS_SITE_PENALTY, scope, top_k),
                )
                return [
                    EmbeddingResult(path=r[0], label=r[1], description=r[2] or "", score=float(r[3]))
                    for r in cur.fetchall()
                ]
    except Exception as e:
        logger.error("search error: %s", e)
        return []


def index_page(path: str, label: str, description: str, tags: List[str], site: str = "default"):
    vec = encode(f"{label} {description} {' '.join(tags or [])}")
    if vec is None:
        logger.warning("Cannot embed %s — model not loaded", path)
        return
    vec_str = "[" + ",".join(f"{v:.6f}" for v in vec.tolist()) + "]"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nav_index (site_id, path, label, description, tags, embedding)
                VALUES (%s,%s,%s,%s,%s,%s::vector)
                ON CONFLICT (site_id, path) DO UPDATE
                  SET label=%s, description=%s, tags=%s, embedding=%s::vector
                """,
                (site, path, label, description, tags, vec_str, label, description, tags, vec_str),
            )
        conn.commit()
