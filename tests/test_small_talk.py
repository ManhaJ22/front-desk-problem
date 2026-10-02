import pytest

from backend import config
from backend.small_talk import small_talk_reply


@pytest.mark.parametrize(
    "message",
    ["hi", "Hello!", "hey there", "Good morning!", "good evening everyone", "Hiya", "howdy folks", "  HELLO  "],
)
def test_greetings_get_the_greeting_reply(message):
    assert small_talk_reply(message) == config.GREETING_RESPONSE


@pytest.mark.parametrize("message", ["thanks", "Thank you!", "thank you so much", "thanks a lot", "ty"])
def test_thanks_get_the_thanks_reply(message):
    assert small_talk_reply(message) == config.THANKS_RESPONSE


@pytest.mark.parametrize(
    "message",
    [
        "high fever today",  # starts with the letters "hi" (the original prefix match caught this)
        "history of the center?",
        "hi, my child is sick",  # greeting + a real question -> full pipeline
        "hello, what time do you close?",
        "thanks, but what about tuition?",
        "Are you open on Veterans Day?",
        "they said hi to me",  # greeting word not at the start
        "",
        "   ",
    ],
)
def test_real_questions_are_not_small_talk(message):
    assert small_talk_reply(message) is None
