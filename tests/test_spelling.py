"""Unit tests for typo self-correction — DB-less (vocabulary degrades to the
synonym map when no database is reachable)."""
from services import spelling


class TestCorrectWord:
    def test_transposed_letters(self):
        assert spelling.correct_word("paymnet") == "payment"

    def test_known_word_untouched(self):
        assert spelling.correct_word("payment") == "payment"

    def test_short_token_untouched(self):
        assert spelling.correct_word("dsh") == "dsh"

    def test_numeric_token_untouched(self):
        assert spelling.correct_word("clm2026") == "clm2026"

    def test_gibberish_untouched(self):
        assert spelling.correct_word("zzzqqqxxx") == "zzzqqqxxx"


class TestCorrectQuery:
    def test_corrects_within_phrase(self):
        assert spelling.correct_query("paymnet history") == "payment history"

    def test_clean_phrase_roundtrips(self):
        assert spelling.correct_query("submit claim") == "submit claim"

    def test_empty_input(self):
        assert spelling.correct_query("") == ""
