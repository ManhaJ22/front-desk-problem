"""Mechanical adherence check: are the model's claimed facts actually in the sources?

Deliberately NOT an LLM call (decision log #3). Each claimed fact is tokenized
and matched against each retrieved chunk on its own; a fact is supported only if
one single chunk contains enough of its words AND every one of its numbers.
"""

import re
from dataclasses import dataclass, field
from typing import Protocol

from backend.config import FACT_TOKEN_MATCH_RATIO

_TOKEN = re.compile(r"\d+(?:[.:,]\d+)*|[a-z]+")

STOPWORDS = frozenset(
    """
    a an the and or but if of to in on at by for from with as is are was were be been
    being it its this that these those there their they them we our us you your he she
    his her i me my can could will would should may might must do does did done have has
    had not no so than then too very just also about into over under up down out per any
    all each every some such only own same other more most what which who whom when where
    why how
    """.split()
)


class Source(Protocol):
    id: str
    title: str
    content: str


@dataclass
class AdherenceResult:
    score: float
    matched: list[tuple[str, str]] = field(default_factory=list)  # (fact, chunk_id)
    unmatched: list[str] = field(default_factory=list)


def is_numeric(token: str) -> bool:
    return token[0].isdigit()


def _normalize(token: str) -> str:
    if is_numeric(token):
        token = token.replace(",", "")  # 2,150 -> 2150
        if token.endswith(":00"):  # 7:00 -> 7, so "7 AM" matches "7:00 AM"
            token = token[:-3]
        return token
    if len(token) > 3 and token.endswith("s"):  # crude plural folding
        token = token[:-1]
    return token


def tokenize(text: str) -> list[str]:
    tokens = (_normalize(t) for t in _TOKEN.findall(text.lower()))
    return [t for t in tokens if t not in STOPWORDS]


def fact_matches(fact: str, chunk_text: str) -> bool:
    fact_tokens = set(tokenize(fact))
    if not fact_tokens:
        return False
    chunk_tokens = set(tokenize(chunk_text))
    numbers = {t for t in fact_tokens if is_numeric(t)}
    if not numbers <= chunk_tokens:
        return False
    found = len(fact_tokens & chunk_tokens)
    return found / len(fact_tokens) >= FACT_TOKEN_MATCH_RATIO


def unsupported_numbers(answer: str, chunks: list[Source]) -> list[str]:
    """Numbers written in the answer text that appear in none of the sources (decision log #23).

    Catches numbers the model wrote but didn't list as a claimed fact. Matching is per
    number across all chunks (the claimed-fact check already enforces single-chunk support).
    """
    source_tokens = {t for c in chunks for t in tokenize(f"{c.title}\n{c.content}")}
    missing = [t for t in tokenize(answer) if is_numeric(t) and t not in source_tokens]
    return list(dict.fromkeys(missing))  # de-duplicate, keep order


def check(facts: list[str], chunks: list[Source], answer: str = "") -> AdherenceResult:
    """Score = matched / (claimed facts + unsupported answer numbers).

    Zero claimed facts scores 0.0 (architecture item C).
    """
    if not facts:
        return AdherenceResult(score=0.0)
    result = AdherenceResult(score=0.0)
    for fact in facts:
        chunk_id = next(
            (c.id for c in chunks if fact_matches(fact, f"{c.title}\n{c.content}")),
            None,
        )
        if chunk_id is None:
            result.unmatched.append(fact)
        else:
            result.matched.append((fact, chunk_id))
    bad_numbers = unsupported_numbers(answer, chunks)
    result.unmatched.extend(f'Answer says "{n}", which isn\'t in the handbook' for n in bad_numbers)
    result.score = len(result.matched) / (len(facts) + len(bad_numbers))
    return result
