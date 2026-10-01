"""Static keyword urgency detection. No LLM, no date parsing (decision log #5)."""

import re

URGENT_PHRASES = [
    "today",
    "tonight",
    "right now",
    "asap",
    "urgent",
    "emergency",
    "this morning",
    "this afternoon",
    "pick up early",
    "pickup early",
    "picking up early",
    "early pickup",
    "running late",
    "on my way",
    "immediately",
]

_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(p).replace(r"\ ", r"\s+") for p in URGENT_PHRASES) + r")\b",
    re.IGNORECASE,
)


def is_urgent(question: str) -> bool:
    return _PATTERN.search(question) is not None
