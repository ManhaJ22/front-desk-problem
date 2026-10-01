"""The ONLY module that talks to Gemini. Tests monkeypatch `embed` and `generate_structured`.

Every call gets one retry on rate-limit/server errors; any failure surfaces as GeminiError
so the pipeline can escalate it as `system_error`.
"""

import time
from collections.abc import Callable
from typing import TypeVar

from google import genai
from google.genai import errors, types
from pydantic import BaseModel

from backend import config

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")

_client: genai.Client | None = None


class GeminiError(Exception):
    """Any failure talking to Gemini (missing key, API error, unparseable response)."""


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise GeminiError("GEMINI_API_KEY is not set")
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _with_retry(call: Callable[[], R]) -> R:
    for attempt in (1, 2):
        try:
            return call()
        except errors.APIError as e:
            if attempt == 1 and e.code in config.RETRY_STATUS_CODES:
                time.sleep(config.RETRY_DELAY_S)
                continue
            raise GeminiError(f"Gemini API error {e.code}: {e}") from e
        except GeminiError:
            raise
        except Exception as e:  # network errors, timeouts
            raise GeminiError(f"Gemini call failed: {e}") from e
    raise AssertionError("unreachable")


def embed(texts: list[str], task_type: str) -> list[list[float]]:
    """task_type: "RETRIEVAL_DOCUMENT" for chunks, "RETRIEVAL_QUERY" for questions."""

    def call() -> list[list[float]]:
        resp = _get_client().models.embed_content(
            model=config.GEMINI_EMBEDDING_MODEL,
            contents=texts,
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=config.EMBEDDING_DIM),
        )
        vectors = [e.values for e in (resp.embeddings or [])]
        if len(vectors) != len(texts) or any(v is None for v in vectors):
            raise GeminiError(f"expected {len(texts)} embeddings, got {len(vectors)}")
        return vectors

    return _with_retry(call)


def generate_structured(prompt: str, system_instruction: str, schema: type[T]) -> T:
    """Structured output only: returns `response.parsed`, never parses `response.text`."""

    def call() -> T:
        resp = _get_client().models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt,
            config={
                "system_instruction": system_instruction,
                "response_mime_type": "application/json",
                "response_schema": schema,
                "temperature": 0,
                # No tools are used; disabling AFC also silences an SDK warning on every call.
                "automatic_function_calling": {"disable": True},
            },
        )
        if not isinstance(resp.parsed, schema):
            raise GeminiError(f"response did not parse as {schema.__name__}")
        return resp.parsed

    return _with_retry(call)
