"""Answer generation + claimed-fact extraction (one structured LLM call).

The claimed facts feed the mechanical adherence check (adherence.py).
"""

from backend import gemini
from backend.retrieval import RetrievedChunk
from backend.schemas import GeneratedAnswer

SYSTEM_INSTRUCTION = """\
You are the front desk assistant for Little Acorns Early Learning Center, answering a parent.

Rules:
- Answer ONLY from the handbook excerpts provided. Never use outside knowledge or guess.
- Be warm, short (2-4 sentences), and plain-spoken. No markdown, no lists.
- If the excerpts do not answer the question, say you're not sure and return an empty
  claimed_facts list.
- Write every number in digits, exactly as the excerpt writes it: "$6", "10:00 AM",
  "(555) 014-2200", "100.4°F". Never spell numbers out ("six dollars", "ten in the morning").

claimed_facts: list EVERY specific factual claim your answer makes (times, dates, dollar
amounts, ages, temperatures, phone numbers, named policies) as short strings, worded as
close to the excerpt's own wording as possible. One claim per string.
"""


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    excerpts = "\n\n".join(f"[{c.title}]\n{c.content}" for c in chunks)
    return f"Handbook excerpts:\n\n{excerpts}\n\nParent's question:\n{question}"


def generate(question: str, chunks: list[RetrievedChunk]) -> GeneratedAnswer:
    return gemini.generate_structured(build_prompt(question, chunks), SYSTEM_INSTRUCTION, GeneratedAnswer)
