from backend import generation
from backend.generation import build_prompt, generate
from backend.retrieval import RetrievedChunk
from backend.schemas import GeneratedAnswer

CHUNKS = [
    RetrievedChunk("holidays", "Holiday Closures", "Little Acorns is OPEN on Veterans Day.", 0.9),
    RetrievedChunk("contact-hours", "Contact Information and Hours", "Open 7:00 AM to 6:00 PM.", 0.7),
]


def test_prompt_contains_question_and_every_titled_excerpt():
    prompt = build_prompt("Are you open on Veterans Day?", CHUNKS)
    assert "Are you open on Veterans Day?" in prompt
    for c in CHUNKS:
        assert f"[{c.title}]\n{c.content}" in prompt


def test_generate_uses_structured_schema_and_grounding_rules(fake_generate):
    expected = GeneratedAnswer(answer="Yes, we're open.", claimed_facts=["OPEN on Veterans Day"])
    fake_generate.responses[GeneratedAnswer] = expected
    assert generate("Are you open on Veterans Day?", CHUNKS) == expected
    prompt, system_instruction, schema = fake_generate.calls[0]
    assert schema is GeneratedAnswer
    assert system_instruction == generation.SYSTEM_INSTRUCTION
    assert "ONLY from the handbook excerpts" in system_instruction
    assert "claimed_facts" in system_instruction
    assert "Write every number in digits" in system_instruction  # decision log #23
