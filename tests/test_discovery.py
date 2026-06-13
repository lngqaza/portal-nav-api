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


class TestDiscoverPageErrorPath:
    """discover_page() must return an error dict when index_page() raises."""

    def test_index_page_failure_returns_error_dict(self, monkeypatch):
        from services import discovery

        monkeypatch.setattr(discovery, "get_conn", lambda: (_ for _ in ()).throw(RuntimeError("DB down")))
        monkeypatch.setattr(discovery, "index_page", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("ONNX fail")))

        result = discovery.discover_page({"path": "/test", "label": "Test"}, "default")
        assert result["indexed"] is False
        assert result["reason"] == "error"
        assert "detail" not in result, "exception detail must not leak to callers"

    def test_index_page_failure_no_detail_key(self, monkeypatch):
        from services import discovery

        def _bad_index(*a, **kw):
            raise RuntimeError("internal path: /var/task/secrets.py line 42")

        monkeypatch.setattr(discovery, "get_conn", lambda: (_ for _ in ()).throw(Exception("hash check")))
        monkeypatch.setattr(discovery, "index_page", _bad_index)

        result = discovery.discover_page({"path": "/page", "label": "Page"}, "site1")
        assert "detail" not in result
        assert result["reason"] == "error"
