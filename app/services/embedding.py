import logging
import os
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_ort_session = None
_tokenizer = None


@dataclass
class EmbeddingResult:
    path: str
    label: str
    description: str
    score: float


def load_model():
    global _ort_session, _tokenizer
    from app.core.config import settings
    model_path = settings.EMBEDDING_MODEL_PATH
    tokenizer_dir = os.path.dirname(model_path)
    if not os.path.exists(model_path):
        logging.warning("Embedding model not found at %s — L1 search disabled", model_path)
        return
    try:
        import onnxruntime as ort
        from transformers import AutoTokenizer
        _ort_session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        _tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir)
        logging.info("Embedding model loaded from %s", model_path)
    except Exception as e:
        logging.error("Failed to load embedding model: %s", e)


def _mean_pool(token_embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    mask_expanded = attention_mask[:, :, None].astype(np.float32)
    sum_embeddings = (token_embeddings * mask_expanded).sum(axis=1)
    sum_mask = mask_expanded.sum(axis=1).clip(min=1e-9)
    embeddings = sum_embeddings / sum_mask
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    return (embeddings / norms).astype(np.float32)


async def encode(text_input: str) -> Optional[np.ndarray]:
    if _ort_session is None or _tokenizer is None:
        return None
    try:
        encoded = _tokenizer(
            text_input, padding=True, truncation=True,
            max_length=128, return_tensors="np"
        )
        outputs = _ort_session.run(None, dict(encoded))
        return _mean_pool(outputs[0], encoded["attention_mask"])[0]
    except Exception as e:
        logging.error("Embedding encode failed: %s", e)
        return None


async def search(query: str, session: AsyncSession, top_k: int = 10) -> List[EmbeddingResult]:
    vec = await encode(query)
    if vec is None:
        return []
    try:
        result = await session.execute(
            text("SELECT path, label, description, 1 - (embedding <=> CAST(:vec AS vector)) as score FROM nav_index WHERE embedding IS NOT NULL ORDER BY embedding <=> CAST(:vec AS vector) LIMIT :k"),
            {"vec": str(vec.tolist()), "k": top_k}
        )
        return [
            EmbeddingResult(path=r.path, label=r.label, description=r.description, score=float(r.score))
            for r in result.fetchall()
        ]
    except Exception as e:
        logging.error("Embedding search failed: %s", e)
        return []


async def index_page(session: AsyncSession, path: str, label: str, description: str, tags: List[str]):
    text_input = f"{label} {description} {' '.join(tags or [])}"
    vec = await encode(text_input)
    if vec is None:
        logging.warning("Could not embed page %s — embedding model not loaded", path)
        return
    try:
        await session.execute(
            text("""
                INSERT INTO nav_index (id, path, label, description, tags, embedding, created_at)
                VALUES (gen_random_uuid(), :p, :l, :d, :t, CAST(:e AS vector), now())
                ON CONFLICT (path) DO UPDATE SET label=:l, description=:d, tags=:t, embedding=CAST(:e AS vector)
            """),
            {"p": path, "l": label, "d": description, "t": tags or [], "e": str(vec.tolist())}
        )
        await session.commit()
        logging.info("Indexed page: %s", path)
    except Exception as e:
        logging.error("Failed to index page %s: %s", path, e)
