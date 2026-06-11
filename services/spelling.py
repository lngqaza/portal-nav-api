"""Free typo self-correction for search queries.

Builds a vocabulary from what is actually searchable — nav_index labels,
descriptions, and tags, plus the intent synonym map — and snaps unknown
query tokens to their nearest vocabulary word with Levenshtein. No model
calls; vocabulary is cached in-process and refreshed lazily.

"paymnet history" -> "payment history".
"""
import logging
import re
import time
from typing import List, Optional

import Levenshtein

from core.db import get_conn
from services.intent import STOPWORDS, SYNONYMS

logger = logging.getLogger(__name__)

# Minimum similarity for a correction. High enough that "claim" never turns
# into "chat", low enough to catch one or two transposed/missing letters.
MIN_RATIO = 0.78
# Never "correct" very short tokens — too ambiguous.
MIN_TOKEN_LEN = 4
VOCAB_TTL_SECONDS = 600

_vocab: dict = {}          # site -> frozenset
_vocab_loaded_at: dict = {}  # site -> monotonic ts


def _build_vocab(site: str) -> frozenset:
    """Collect every searchable word from nav_index + the synonym map."""
    words = set()
    for k, vals in SYNONYMS.items():
        words.add(k)
        words.update(vals)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT lower(label || ' ' || coalesce(description,'') || ' '
                                 || coalesce(array_to_string(tags,' '),''))
                    FROM nav_index WHERE site_id = %s
                    """,
                    (site,),
                )
                for (text,) in cur.fetchall():
                    words.update(w for w in re.findall(r"[a-z]+", text) if len(w) >= 3)
    except Exception as e:
        logger.warning("vocab build failed, using synonym-only vocab: %s", e)
    return frozenset(w for w in words if w not in STOPWORDS)


def get_vocab(site: str = "default") -> frozenset:
    """Cached per-site vocabulary, rebuilt at most every VOCAB_TTL_SECONDS."""
    now = time.monotonic()
    if site not in _vocab or now - _vocab_loaded_at.get(site, 0) > VOCAB_TTL_SECONDS:
        _vocab[site] = _build_vocab(site)
        _vocab_loaded_at[site] = now
    return _vocab[site]


def correct_word(word: str, site: str = "default") -> str:
    """Return the closest vocabulary word, or the word unchanged.

    Known words, stopwords, short tokens, and numbers pass through untouched.
    """
    w = word.lower()
    if len(w) < MIN_TOKEN_LEN or w in STOPWORDS or any(c.isdigit() for c in w):
        return word
    vocab = get_vocab(site)
    if w in vocab:
        return word
    best, best_ratio = None, MIN_RATIO
    for v in vocab:
        # Cheap length pre-filter before computing the ratio
        if abs(len(v) - len(w)) > 2:
            continue
        r = Levenshtein.ratio(w, v)
        if r > best_ratio:
            best, best_ratio = v, r
    return best if best else word


def correct_query(query: str, site: str = "default") -> str:
    """Correct each word of a query; preserves word order and unknown words."""
    parts = re.findall(r"[a-z0-9]+", (query or "").lower())
    if not parts:
        return query
    corrected = [correct_word(p, site) for p in parts]
    return " ".join(corrected)
