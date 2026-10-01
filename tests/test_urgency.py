import pytest

from backend.urgency import URGENT_PHRASES, is_urgent


@pytest.mark.parametrize("phrase", URGENT_PHRASES)
def test_every_phrase_triggers(phrase):
    assert is_urgent(f"Hi, {phrase} — can you help?")


@pytest.mark.parametrize(
    "question",
    [
        "Can I PICK UP EARLY on Friday?",
        "I need to pick  up early",  # extra whitespace
        "Is the center open today?",
    ],
)
def test_case_and_spacing_insensitive(question):
    assert is_urgent(question)


@pytest.mark.parametrize(
    "question",
    [
        "What is the tuition for infants?",
        "Are you open on Veterans Day?",
        "Do you have a holiday schedule for todays' families?",  # 'todays' is not 'today'
    ],
)
def test_non_urgent_questions(question):
    assert not is_urgent(question)


def test_near_misses_dont_trigger():
    assert not is_urgent("The late fee applies to nowhere else")
    assert not is_urgent("Is the latest menu online?")
