"""
L2 invariants — L2-01 through L2-04.
"""
import pytest
from models.navigation import EmbeddingResult


def _candidates(n=3):
    return [
        EmbeddingResult(path=f"/path/{i}", label=f"Label {i}", description=f"Description {i}", score=0.5 - i * 0.1)
        for i in range(n)
    ]


# ── L2-01: rerank never returns result below L2_THRESHOLD ────────────────────

def test_l201_rerank_confidence_never_below_threshold(reranker_model_loaded, settings_override):
    """rerank() never returns a candidate with score < L2_THRESHOLD."""
    from services.reranker import rerank
    with settings_override(L2_THRESHOLD=0.5):
        result = rerank("test query", _candidates(3))
    if result is not None:
        assert result.score >= 0.5, f"Returned score {result.score} < threshold 0.5"


def test_l201_rerank_returns_none_when_all_below_threshold(settings_override):
    """rerank() returns None when all candidates score below L2_THRESHOLD."""
    from services.reranker import rerank
    import services.reranker as rer
    import numpy as np

    # Mock ONNX to return very low scores
    original_session = rer._session
    try:
        mock_session = type("S", (), {
            "get_inputs": lambda self: [type("I", (), {"name": "input_ids"})()],
            "run": lambda self, out, inp: [np.array([[[-10.0]]]),],
        })()
        rer._session = mock_session

        with settings_override(L2_THRESHOLD=0.5):
            result = rerank("test", _candidates(3))

        assert result is None, f"Expected None for low-scoring candidates, got {result}"
    finally:
        rer._session = original_session


# ── L2-02: rerank returns None on empty list ─────────────────────────────────

def test_l202_rerank_returns_none_on_empty_candidates():
    """rerank() returns None — never raises — when candidates list is empty."""
    from services.reranker import rerank
    result = rerank("test query", [])
    assert result is None


# ── L2-03: graceful fallback when model absent ───────────────────────────────

def test_l203_graceful_fallback_when_model_absent(settings_override):
    """When reranker model is absent, rerank() falls back — never raises."""
    from services.reranker import rerank
    import services.reranker as rer

    original_session = rer._session
    original_tokenizer = rer._tokenizer
    try:
        rer._session = None
        rer._tokenizer = None
        candidates = _candidates(3)
        # With L2_THRESHOLD low enough, should return best L1 candidate
        with settings_override(L2_THRESHOLD=0.0):
            result = rerank("test", candidates)
        # Must not raise; may return None or a candidate
        assert result is None or result in candidates
    finally:
        rer._session = original_session
        rer._tokenizer = original_tokenizer


# ── L2-04: rerank returns one of the input candidates ────────────────────────

def test_l204_rerank_returns_input_candidate(reranker_model_loaded, settings_override):
    """rerank() always returns one of the items from the input candidates list."""
    from services.reranker import rerank
    candidates = _candidates(3)
    with settings_override(L2_THRESHOLD=0.0):
        result = rerank("label 0", candidates)
    if result is not None:
        assert result in candidates, "rerank returned an object not in the input candidates list"
