"""L2: ONNX cross-encoder re-ranker. Only fires when L1 confidence is low."""
import logging
import os
from typing import List, Optional

from core.config import settings
from models.navigation import EmbeddingResult

logger = logging.getLogger(__name__)

_session = None
_tokenizer = None


def load_reranker():
    global _session, _tokenizer
    path = settings.RERANKER_MODEL_PATH
    if not os.path.exists(path):
        logger.warning("Reranker not found at %s — L2 disabled", path)
        return
    try:
        import onnxruntime as ort
        from transformers import AutoTokenizer
        _session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        _tokenizer = AutoTokenizer.from_pretrained(os.path.dirname(path))
        logger.info("Reranker loaded from %s", path)
    except Exception as e:
        logger.error("Reranker load failed: %s", e)


def rerank(query: str, candidates: List[EmbeddingResult]) -> Optional[EmbeddingResult]:
    if not candidates:
        return None
    if not _session or not _tokenizer:
        return candidates[0] if candidates[0].score >= settings.L2_THRESHOLD else None
    try:
        scores = []
        valid_inputs = {inp.name for inp in _session.get_inputs()}
        for c in candidates:
            raw = _tokenizer(
                query, c.label + " " + c.description,
                return_tensors="np", truncation=True, max_length=128, padding=True,
            )
            inp = {k: v for k, v in raw.items() if k in valid_inputs}
            out = _session.run(None, inp)
            scores.append(float(out[0][0][0]))
        best_idx = scores.index(max(scores))
        best = candidates[best_idx]
        best.score = max(scores)
        return best if best.score >= settings.L2_THRESHOLD else None
    except Exception as e:
        logger.error("rerank error: %s", e)
        return candidates[0] if candidates else None
