"""Free, in-process natural-language intent understanding.

Turns conversational questions ("where do I log a claim?") into the intent
core ("log a claim") and an expanded keyword set ("submit", "claim", ...)
so every cascade layer matches on what the user MEANS, not the literal
phrasing. Pure stdlib — no model calls, no cost, <1ms.
"""
import re

# Question scaffolding that carries zero navigation intent. Stripped
# repeatedly from the front of the query until none match, so stacked
# phrasings like "please can you show me where to ..." also reduce.
_SCAFFOLD_PREFIXES = [
    r"please",
    r"hi|hello|hey",
    r"can (you|i)( please)?",
    r"could (you|i)( please)?",
    r"how (do|can|would|to) (i|we|you)?",
    r"how to",
    r"where (do|can|would|to|is|are|did) (i|we|you)?",
    r"where to",
    r"where('s| is| are)?",
    r"what('s| is| are)? (the )?(page|place|link) (for|to)",
    r"i (want|need|would like|wish|am trying|'m trying) to",
    r"i want|i need",
    r"show me",
    r"take me to",
    r"go to",
    r"navigate to",
    r"find( me)?( the)?",
    r"help( me)?( with)?( to)?",
    r"looking for",
    r"the page (for|to|where)",
]
_PREFIX_RE = re.compile(
    r"^\s*(?:" + "|".join("(?:%s)" % p for p in _SCAFFOLD_PREFIXES) + r")\s+",
    re.IGNORECASE,
)

# Filler words that survive prefix stripping but carry no intent.
STOPWORDS = frozenset(
    "a an and are can do does for from how i in is it me my of on or our "
    "page the their this to want we what when where which who why will "
    "with would you your".split()
)

# Domain synonym map: user vocabulary → the vocabulary used in nav_index
# labels/descriptions. Keys and values are single lowercase tokens; each
# matched key adds its expansions to the keyword set (the original token is
# always kept too).
SYNONYMS = {
    "log": ["submit", "claim"],
    "lodge": ["submit"],
    "file": ["submit"],
    "report": ["submit"],
    "register": ["submit"],
    "open": ["submit", "new"],
    "track": ["status", "progress"],
    "progress": ["status"],
    "money": ["payment", "premium"],
    "pay": ["payment", "premium"],
    "bill": ["payment", "premium"],
    "owe": ["payment", "balance"],
    "refund": ["payment"],
    "receipt": ["payment", "history", "statement"],
    "transaction": ["payment", "history"],
    "cert": ["certificate"],
    "tax": ["certificate", "statement"],
    "cancel": ["stop"],
    "stop": ["cancel"],
    "update": ["change", "edit", "manage"],
    "change": ["update", "edit", "manage"],
    "edit": ["update", "profile"],
    "fix": ["update", "change"],
    "login": ["password", "account"],
    "signin": ["password", "account"],
    "pin": ["password"],
    "nominee": ["beneficiary"],
    "dependant": ["beneficiary"],
    "address": ["profile", "details"],
    "phone": ["profile", "contact"],
    "email": ["profile", "contact"],
    "talk": ["contact", "support", "chat"],
    "speak": ["contact", "support", "chat"],
    "call": ["contact", "support"],
    "agent": ["support", "chat", "contact"],
    "human": ["support", "contact"],
    "question": ["faq", "support", "help"],
    "complain": ["complaint", "support"],
    "unhappy": ["complaint", "support"],
    "cover": ["policy", "benefits"],
    "coverage": ["policy", "benefits"],
    "insurance": ["policy", "cover"],
    "premium": ["payment", "policy"],
    "renew": ["policy", "renewal"],
    "car": ["vehicle", "motor"],
    "motor": ["vehicle"],
    "house": ["home", "contents"],
    "medical": ["health", "benefits"],
    "doctor": ["health", "medical"],
    "funeral": ["life", "benefits"],
    "download": ["documents", "statement"],
    "upload": ["documents"],
    "paperwork": ["documents"],
    "form": ["documents", "submit"],
    "bank": ["banking", "debit"],
    "debit": ["banking", "payment"],
    "eft": ["banking", "payment"],
}


def intent_core(query: str) -> str:
    """Strip question scaffolding and punctuation, returning the intent core.

    "Where do I log a claim?" -> "log a claim". Falls back to the cleaned
    original if stripping would consume the whole query.
    """
    q = re.sub(r"[?!.]+\s*$", "", (query or "").strip().lower())
    core = q
    # Strip stacked prefixes ("please can you show me where to ...")
    for _ in range(6):
        stripped = _PREFIX_RE.sub("", core)
        if stripped == core:
            break
        core = stripped.strip()
    return core if core else q


def tokens(query: str) -> list:
    """Meaningful lowercase tokens from a query: stopwords and 1-2 char
    fragments dropped, singular variants added for plurals so "claims"
    also matches "Claim"."""
    words = [
        w for w in re.findall(r"[a-z0-9]+", (query or "").lower())
        if len(w) >= 3 and w not in STOPWORDS
    ]
    out = []
    for w in words:
        if w not in out:
            out.append(w)
        if w.endswith("s") and len(w) >= 4 and w[:-1] not in out:
            out.append(w[:-1])
    return out


def expanded_tokens(query: str) -> list:
    """tokens() plus domain-synonym expansions, originals first."""
    base = tokens(query)
    out = list(base)
    for t in base:
        for syn in SYNONYMS.get(t, []):
            if syn not in out:
                out.append(syn)
    return out
