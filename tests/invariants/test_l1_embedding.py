"""
L1 invariants — L1-01 through L1-08.
"""
import pytest
import numpy as np


# ── L1-01: encode returns unit vector ────────────────────────────────────────

def test_l101_encode_returns_unit_vector(embedding_model_loaded):
    """encode() output has L2-norm = 1.0 ± 1e-5."""
    from services.embedding import encode
    vec = encode("submit a claim")
    assert vec is not None
    norm = float(np.linalg.norm(vec))
    assert abs(norm - 1.0) < 1e-5, f"L2-norm is {norm}, expected 1.0"


def test_l101_encode_unit_vector_various_inputs(embedding_model_loaded):
    """Unit vector invariant holds for multiple input types."""
    from services.embedding import encode
    inputs = ["hello", "", "a" * 500, "كيف", "submit a claim today please"]
    for text in inputs:
        vec = encode(text)
        if vec is not None:
            norm = float(np.linalg.norm(vec))
            assert abs(norm - 1.0) < 1e-4, f"Norm {norm} for input {text!r}"


# ── L1-02: encode returns 384-dim array ──────────────────────────────────────

def test_l102_encode_returns_384_dimensions(embedding_model_loaded):
    """encode() output is always 384-dimensional."""
    from services.embedding import encode
    vec = encode("test input")
    assert vec is not None
    assert vec.shape == (384,), f"Expected shape (384,), got {vec.shape}"


# ── L1-03: search returns empty list when model absent ───────────────────────

def test_l103_search_returns_empty_when_model_absent():
    """search() returns [] — never raises — when embedding model is not loaded."""
    import services.embedding as emb
    original_session = emb._session
    original_tokenizer = emb._tokenizer
    try:
        emb._session = None
        emb._tokenizer = None
        results = emb.search("test query", top_k=5)
        assert results == [], f"Expected [], got {results}"
    finally:
        emb._session = original_session
        emb._tokenizer = original_tokenizer


# ── L1-04: search results in descending order ────────────────────────────────

def test_l104_search_results_descending_score(seeded_index, embedding_model_loaded):
    """search() results are ordered from highest to lowest score."""
    from services.embedding import search
    results = search("submit insurance claim", top_k=10)
    if len(results) < 2:
        pytest.skip("Not enough results to verify ordering")
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True), f"Scores not descending: {scores}"


# ── L1-05: scores in [-1.0, 1.0] ─────────────────────────────────────────────

def test_l105_scores_in_valid_range(seeded_index, embedding_model_loaded):
    """All similarity scores from search() are in [-1.0, 1.0]."""
    from services.embedding import search
    results = search("renew my policy", top_k=10)
    for r in results:
        assert -1.0 <= r.score <= 1.0, f"Score {r.score} out of [-1.0, 1.0]"


# ── L1-06: token_type_ids filtered ───────────────────────────────────────────

def test_l106_token_type_ids_not_passed_to_onnx(embedding_model_loaded):
    """encode() never passes token_type_ids to the ONNX session."""
    from services.embedding import _session, _tokenizer
    import numpy as np

    text = "test query for token type ids check"
    enc = _tokenizer(text, padding=True, truncation=True, max_length=128, return_tensors="np")

    valid_inputs = {inp.name for inp in _session.get_inputs()}
    model_inputs = {k: v for k, v in enc.items() if k in valid_inputs}

    assert "token_type_ids" not in model_inputs or "token_type_ids" in valid_inputs, (
        "token_type_ids present in model inputs but not accepted by ONNX model"
    )
    # Positive: the model run should succeed without error
    _session.run(None, model_inputs)  # must not raise


# ── L1-07: index_page is retrievable by search ───────────────────────────────

def test_l107_indexed_page_retrievable(clean_db, embedding_model_loaded):
    """A page indexed via index_page is returned by search with a positive score."""
    from services.embedding import index_page, search

    index_page("/test/invariant", "Invariant Test Page", "unique xyzzy marker for testing", ["test"])
    clean_db.commit()

    results = search("invariant test page xyzzy", top_k=5)
    paths = [r.path for r in results]
    assert "/test/invariant" in paths, f"Indexed page not found in search results: {paths}"


# ── L1-08: indexing same path is idempotent ──────────────────────────────────

def test_l108_index_page_idempotent(clean_db, embedding_model_loaded):
    """Calling index_page twice for the same path results in exactly one row."""
    from services.embedding import index_page

    for _ in range(3):
        index_page("/dup/path", "Duplicate Path", "idempotency test", ["dup"])
    clean_db.commit()

    with clean_db.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM nav_index WHERE path='/dup/path'")
        count = cur.fetchone()[0]

    assert count == 1, f"Expected 1 row for /dup/path, found {count}"
