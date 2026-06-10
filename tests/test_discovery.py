"""Unit tests for self-discovery sanitisation and hashing — DB-less."""
import pytest

from services.discovery import sanitise, content_hash


class TestSanitise:
    def test_valid_payload(self):
        p = sanitise({"path": "/claims.html", "label": "My Claims",
                      "description": "View  all\nclaims", "tags": ["Claims", "claims", "x"]})
        assert p["path"] == "/claims.html"
        assert p["description"] == "View all claims"
        assert p["tags"] == ["claims", "x"]  # deduped and lowercased

    def test_strips_query_and_fragment(self):
        assert sanitise({"path": "/a.html?x=1#top", "label": "A"})["path"] == "/a.html"

    def test_rejects_relative_path(self):
        with pytest.raises(ValueError):
            sanitise({"path": "claims.html", "label": "A"})

    def test_rejects_traversal(self):
        with pytest.raises(ValueError):
            sanitise({"path": "/../etc", "label": "A"})

    def test_rejects_missing_label(self):
        with pytest.raises(ValueError):
            sanitise({"path": "/a.html", "label": "  "})

    def test_caps_lengths(self):
        p = sanitise({"path": "/a.html", "label": "L" * 500, "description": "D" * 1000,
                      "tags": [str(i) * 50 for i in range(30)]})
        assert len(p["label"]) == 120 and len(p["description"]) == 400 and len(p["tags"]) <= 12


class TestContentHash:
    def test_stable(self):
        a = {"path": "/a", "label": "A", "description": "d", "tags": ["t"]}
        assert content_hash(a) == content_hash(dict(a))

    def test_changes_with_content(self):
        a = {"path": "/a", "label": "A", "description": "d", "tags": ["t"]}
        b = dict(a, description="d2")
        assert content_hash(a) != content_hash(b)
