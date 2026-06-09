"""L1: ONNX sentence-transformer — encode + cosine search against nav_index."""
import logging
import os
from typing import List, Optional

import numpy as np

from core.config import settings
from core.db import get_conn
from models.navigation import EmbeddingResult

logger = logging.getLogger(__name__)

_session = None
_tokenizer = None


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
        out = _session.run(None, dict(enc))
        mask = enc["attention_mask"][:, :, None].astype(np.float32)
        emb = (out[0] * mask).sum(1) / mask.sum(1).clip(min=1e-9)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        return (emb / norms)[0].astype(np.float32)
    except Exception as e:
        logger.error("encode error: %s", e)
        return None


def search(query: str, top_k: int = 10) -> List[EmbeddingResult]:
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
                           1 - (embedding <=> %s::vector) AS score
                    FROM nav_index
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (vec_str, vec_str, top_k),
                )
                return [
                    EmbeddingResult(path=r[0], label=r[1], description=r[2] or "", score=float(r[3]))
                    for r in cur.fetchall()
                ]
    except Exception as e:
        logger.error("search error: %s", e)
        return []


def index_page(path: str, label: str, description: str, tags: List[str]):
    vec = encode(f"{label} {description} {' '.join(tags or [])}")
    if vec is None:
        logger.warning("Cannot embed %s — model not loaded", path)
        return
    vec_str = "[" + ",".join(f"{v:.6f}" for v in vec.tolist()) + "]"
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nav_index (path, label, description, tags, embedding)
                VALUES (%s,%s,%s,%s,%s::vector)
                ON CONFLICT (path) DO UPDATE
                  SET label=%s, description=%s, tags=%s, embedding=%s::vector
                """,
                (path, label, description, tags, vec_str, label, description, tags, vec_str),
            )
        conn.commit()
