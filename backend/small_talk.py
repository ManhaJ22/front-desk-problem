"""Greetings and thanks, answered before the pipeline: no retrieval, no LLM (decision log #40).

Whole-word matching only. A message counts as small talk only if, after the greeting/thanks
phrase, nothing but filler words remain — so "hi there!" matches but "high fever today",
"history of the center?" and "hi, my child is sick" do not.
"""

import re

from backend import config

GREETING_PATTERNS = {"hi", "hello", "hey", "good morning", "good afternoon", "good evening", "hiya", "howdy"}
THANKS_PATTERNS = {"thanks", "thank you", "thank you so much", "thanks so much", "thanks a lot", "thx", "ty"}

# Words allowed around a greeting/thanks without turning it into a real question.
FILLER = {"there", "everyone", "all", "folks", "team", "again", "very", "much", "so", "a", "lot", "you", "guys"}


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z']+", text.lower())


def _is_only(words: list[str], patterns: set[str]) -> bool:
    for pattern in sorted(patterns, key=len, reverse=True):  # longest phrase first
        p = pattern.split()
        if words[: len(p)] == p:
            return all(w in FILLER for w in words[len(p) :])
    return False


def small_talk_reply(question: str) -> str | None:
    """Canned reply if the whole message is a greeting or thanks, else None."""
    words = _words(question)
    if not words or len(words) > 5:
        return None
    if _is_only(words, GREETING_PATTERNS):
        return config.GREETING_RESPONSE
    if _is_only(words, THANKS_PATTERNS):
        return config.THANKS_RESPONSE
    return None
