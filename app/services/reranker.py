import logging
import os
from typing import List, Optional

from app.services.embedding import EmbeddingResult

_reranker_session = None
_reranker_tokenizer = None


def load_reranker():
    global _reranker_session, _reranker_tokenizer
    from app.core.config import settings
    model_path = settings.RERANKER_MODEL_PATH
    tokenizer_dir = os.path.dirname(model_path)
    if not os.path.exists(model_path):
        logging.warning("Reranker model not found at %s — L2 reranking disabled", model_path)
        return
    try:
        import onnxruntime as ort
        from transformers import AutoTokenizer
        _reranker_session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        _reranker_tokenizer = AutoTokenizer.from_pretrained(tokenizer_dir)
        logging.info("Reranker model loaded from %s", model_path)
    except Exception as e:
        logging.error("Failed to load reranker model: %s", e)


async def rerank(query: str, candidates: List[EmbeddingResult], session) -> Optional[EmbeddingResult]:
    from app.core.config import settings
    if not candidates:
        return None
    if _reranker_session is None or _reranker_tokenizer is None:
        logging.debug("Reranker not loaded, returning top L1 candidate")
        return candidates[0] if candidates[0].score >= settings.L2_THRESHOLD else None
    try:
        import numpy as np
        scores = []
        for c in candidates:
            pair_text = c.label + " " + c.description
            inputs = _reranker_tokenizer(
                query, pair_text, return_tensors="np",
                truncation=True, max_length=128, padding=True
            )
            output = _reranker_session.run(None, dict(inputs))
            score = float(output[0][0][0])
            scores.append(score)
        best_idx = scores.index(max(scores))
        best_score = max(scores)
        best = candidates[best_idx]
        best.score = best_score
        return best if best_score >= settings.L2_THRESHOLD else None
    except Exception as e:
        logging.error("Reranker failed: %s", e)
        return candidates[0] if candidates else None
