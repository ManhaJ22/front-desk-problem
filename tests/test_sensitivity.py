import pytest

from backend import sensitivity
from backend.schemas import SensitivityCategory, SensitivityResult
from backend.sensitivity import classify, is_sensitive, normalized

SENSITIVE_CATEGORIES = [c for c in SensitivityCategory if c is not SensitivityCategory.none]


def result(category: SensitivityCategory, score: int) -> SensitivityResult:
    return SensitivityResult(category=category, score=score, rationale="r")


def test_normalized_maps_1_to_5_onto_0_to_1():
    assert [normalized(s) for s in range(1, 6)] == [0.0, 0.25, 0.5, 0.75, 1.0]


@pytest.mark.parametrize("category", SENSITIVE_CATEGORIES)
@pytest.mark.parametrize("score, expected", [(1, False), (2, False), (3, True), (4, True), (5, True)])
def test_sensitive_category_counts_from_score_3(category, score, expected):
    # Decision log #25: a category tag scored 1-2 ("how do I call her in sick?") doesn't force escalation.
    assert is_sensitive(result(category, score)) is expected


@pytest.mark.parametrize("score, expected", [(1, False), (2, False), (3, False), (4, True), (5, True)])
def test_category_none_uses_the_070_threshold(score, expected):
    # (score-1)/4 >= 0.70  <=>  score >= 4
    assert is_sensitive(result(SensitivityCategory.none, score)) is expected


def test_classifier_is_told_to_classify_by_need_not_topic():
    assert "by what the parent NEEDS" in sensitivity.SYSTEM_INSTRUCTION
    assert "call my daughter in sick" in sensitivity.SYSTEM_INSTRUCTION


def test_classify_sends_question_only_with_schema(fake_generate):
    fake_generate.responses[SensitivityResult] = result(SensitivityCategory.health, 5)
    out = classify("My child has a fever, can they come in?")
    assert out.category is SensitivityCategory.health
    prompt, system_instruction, schema = fake_generate.calls[0]
    assert schema is SensitivityResult
    assert "My child has a fever, can they come in?" in prompt
    assert "Handbook" not in prompt  # classification never sees handbook text
    assert system_instruction == sensitivity.SYSTEM_INSTRUCTION


@pytest.mark.parametrize("raw, clamped", [(0, 1), (7, 5), (3, 3)])
def test_classify_clamps_out_of_range_scores(fake_generate, raw, clamped):
    fake_generate.responses[SensitivityResult] = result(SensitivityCategory.none, raw)
    assert classify("q").score == clamped


def test_classifier_is_told_how_to_judge_urgency_in_context():
    # Decision log #44: a time word alone isn't urgent.
    assert "is_urgent is true only if" in sensitivity.SYSTEM_INSTRUCTION
    assert "how is the weather today?" in sensitivity.SYSTEM_INSTRUCTION
