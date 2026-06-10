"""Unit tests for the free NLU intent layer — no DB, no models, no network."""
from services import intent


class TestIntentCore:
    def test_strips_where_question(self):
        assert intent.intent_core("Where do I log a claim?") == "log a claim"

    def test_strips_where_to(self):
        assert intent.intent_core("where to log claims") == "log claims"

    def test_strips_how_do_i(self):
        assert intent.intent_core("How do I change my password?") == "change my password"

    def test_strips_stacked_scaffolding(self):
        assert intent.intent_core("please can you show me where to make a payment") == "make a payment"

    def test_strips_i_want_to(self):
        assert intent.intent_core("I want to submit a claim") == "submit a claim"

    def test_plain_query_unchanged(self):
        assert intent.intent_core("submit a claim") == "submit a claim"

    def test_partial_word_unchanged(self):
        assert intent.intent_core("dash") == "dash"

    def test_never_returns_empty(self):
        # Scaffolding-only input must fall back to the cleaned original
        assert intent.intent_core("where to") != ""

    def test_handles_empty_input(self):
        assert intent.intent_core("") == ""


class TestTokens:
    def test_drops_stopwords(self):
        assert intent.tokens("where to log claims") == ["log", "claims", "claim"]

    def test_adds_singular_variant(self):
        assert "claim" in intent.tokens("claims")

    def test_drops_short_fragments(self):
        assert intent.tokens("go to it") == []


class TestExpandedTokens:
    def test_log_expands_to_submit(self):
        out = intent.expanded_tokens("log claims")
        assert "submit" in out and "log" in out and "claims" in out

    def test_originals_come_first(self):
        out = intent.expanded_tokens("log claims")
        assert out.index("log") < out.index("submit")

    def test_money_expands_to_payment(self):
        assert "payment" in intent.expanded_tokens("money owed")

    def test_no_synonym_passthrough(self):
        assert intent.expanded_tokens("dashboard") == ["dashboard"]
