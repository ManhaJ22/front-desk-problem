"""Shared fixtures. No test ever calls Gemini: `embed` and `generate_structured` are faked."""

import math
import zlib

import pytest

from backend import config, db, gemini
from backend.adherence import tokenize

FAKE_DIM = 256


def fake_vector(text: str) -> list[float]:
    """Deterministic bag-of-words vector: texts sharing words have high cosine similarity."""
    v = [0.0] * FAKE_DIM
    for token in tokenize(text):
        v[zlib.crc32(token.encode()) % FAKE_DIM] += 1.0
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]


class FakeEmbedder:
    def __init__(self):
        self.calls: list[tuple[list[str], str]] = []

    def __call__(self, texts: list[str], task_type: str) -> list[list[float]]:
        self.calls.append((list(texts), task_type))
        return [fake_vector(t) for t in texts]


class FakeGenerator:
    """Returns a configured response per schema; fails loudly on unexpected LLM calls.

    Configure with `fake_generate.responses[SchemaClass] = instance | Exception | callable(prompt)`.
    """

    def __init__(self):
        self.responses: dict[type, object] = {}
        self.calls: list[tuple[str, str, type]] = []

    def __call__(self, prompt: str, system_instruction: str, schema: type):
        self.calls.append((prompt, system_instruction, schema))
        if schema not in self.responses:
            raise AssertionError(f"unexpected LLM call for {schema.__name__}")
        response = self.responses[schema]
        if isinstance(response, Exception):
            raise response
        return response(prompt) if callable(response) and not isinstance(response, type) else response

    def calls_for(self, schema: type) -> int:
        return sum(1 for _, _, s in self.calls if s is schema)


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()


@pytest.fixture(autouse=True)
def fake_embed(monkeypatch) -> FakeEmbedder:
    fake = FakeEmbedder()
    monkeypatch.setattr(gemini, "embed", fake)
    return fake


@pytest.fixture(autouse=True)
def fake_generate(monkeypatch) -> FakeGenerator:
    fake = FakeGenerator()
    monkeypatch.setattr(gemini, "generate_structured", fake)
    return fake
