"""
CFG invariants — CFG-01 through CFG-04.
"""
import pytest


# ── CFG-01: thresholds in (0.0, 1.0] ─────────────────────────────────────────

def test_cfg01_thresholds_in_valid_range():
    """All threshold values are in (0.0, 1.0]."""
    from core.config import settings
    for attr in ("HOT_PATH_THRESHOLD", "L1_THRESHOLD", "L2_THRESHOLD"):
        val = getattr(settings, attr)
        assert 0.0 < val <= 1.0, f"{attr}={val} is outside (0.0, 1.0]"


# ── CFG-02: MAX_HOT_PATHS positive ───────────────────────────────────────────

def test_cfg02_max_hot_paths_positive():
    """MAX_HOT_PATHS is always a positive integer."""
    from core.config import settings
    assert isinstance(settings.MAX_HOT_PATHS, int)
    assert settings.MAX_HOT_PATHS > 0


# ── CFG-03: API_KEYS non-empty (live service only) ───────────────────────────

def test_cfg03_api_keys_non_empty():
    """API_KEYS list is never empty when the service is configured."""
    from core.config import settings
    import os
    if not os.environ.get("API_KEYS"):
        pytest.skip("API_KEYS not set in test environment")
    assert len(settings.API_KEYS) > 0
    assert all(k.strip() for k in settings.API_KEYS), "API_KEYS contains blank entries"


# ── Settings override does not mutate permanently ────────────────────────────

def test_settings_override_restores_original(settings_override):
    """settings_override context manager restores original values on exit."""
    from core.config import settings
    original = settings.HOT_PATH_THRESHOLD
    with settings_override(HOT_PATH_THRESHOLD=0.99):
        assert settings.HOT_PATH_THRESHOLD == 0.99
    assert settings.HOT_PATH_THRESHOLD == original, "settings_override did not restore original value"
