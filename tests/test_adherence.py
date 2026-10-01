from dataclasses import dataclass

from backend.adherence import check, fact_matches, tokenize, unsupported_numbers


@dataclass
class Chunk:
    id: str
    title: str
    content: str


TUITION = Chunk(
    "tuition",
    "Monthly Tuition by Age Group",
    "Infants (6 weeks to 12 months) $2,150 per month; Toddlers (12 to 24 months) $1,950 per month.",
)
HOURS = Chunk(
    "contact-hours",
    "Contact Information and Hours",
    "The center is open Monday through Friday from 7:00 AM to 6:00 PM. Call (555) 014-2200.",
)
ILLNESS = Chunk(
    "illness",
    "Illness and Fever Policy",
    "Children with a fever of 100.4°F or higher must be fever-free for 24 hours before returning.",
)


def test_exact_fact_matches():
    assert fact_matches("Infants (6 weeks to 12 months) $2,150 per month", TUITION.content)


def test_paraphrase_with_same_numbers_matches():
    assert fact_matches("infant tuition is $2,150 a month", TUITION.content)


def test_wrong_number_fails_even_if_words_match():
    assert not fact_matches("Infants $1,850 per month", TUITION.content)


def test_phone_number_must_match_exactly():
    assert fact_matches("call (555) 014-2200", HOURS.content)
    assert not fact_matches("call (555) 014-2201", HOURS.content)


def test_number_normalization():
    assert tokenize("7:00 AM") == tokenize("7 AM")
    assert tokenize("$2,150") == tokenize("2150")
    assert "100.4" in tokenize("100.4°F")
    assert "7:30" in tokenize("7:30 AM")


def test_unrelated_fact_fails():
    assert not fact_matches("swim lessons are offered every summer", TUITION.content)


def test_fact_stitched_from_two_chunks_fails():
    # "$2,150" lives in TUITION, "6:00 PM" lives in HOURS; no single chunk has both.
    result = check(["Infants cost $2,150 per month until 6:00 PM"], [TUITION, HOURS])
    assert result.score == 0.0
    assert result.unmatched == ["Infants cost $2,150 per month until 6:00 PM"]


def test_check_scores_fraction_and_records_chunk():
    facts = ["fever of 100.4°F or higher", "open from 7:00 AM to 6:00 PM", "free parking on site"]
    result = check(facts, [TUITION, HOURS, ILLNESS])
    assert result.score == 2 / 3
    assert ("fever of 100.4°F or higher", "illness") in result.matched
    assert ("open from 7:00 AM to 6:00 PM", "contact-hours") in result.matched
    assert result.unmatched == ["free parking on site"]


def test_zero_facts_scores_zero():
    assert check([], [TUITION]).score == 0.0


def test_title_counts_as_source_text():
    assert fact_matches("Illness and Fever Policy", f"{ILLNESS.title}\n{ILLNESS.content}")


# --- answer-number check (decision log #23) -------------------------------------------------

LUNCH = Chunk(
    "forgotten-lunch",
    "Forgotten Lunch / Backup Lunch",
    "The center can provide a backup lunch for $6. Let the front office know by 10:00 AM.",
)


def test_unlisted_wrong_number_in_answer_is_caught():
    # The model listed only a correct fact, but the prose also states a price the handbook doesn't have.
    result = check(["backup lunch for $6"], [LUNCH], answer="A backup lunch is $6, or $8 with dessert.")
    assert result.unmatched == ['Answer says "8", which isn\'t in the handbook']
    assert result.score == 0.5  # 1 matched / (1 fact + 1 unsupported number)


def test_numbers_present_in_any_chunk_pass():
    answer = "A backup lunch is $6 if you call by 10:00 AM; we're open 7 AM to 6 PM."
    assert check(["backup lunch for $6"], [LUNCH, HOURS], answer=answer).score == 1.0


def test_answer_number_normalization_matches_source_format():
    assert unsupported_numbers("Infant tuition is $2,150 per month.", [TUITION]) == []
    assert unsupported_numbers("Call us by 10 AM.", [LUNCH]) == []  # 10:00 AM in source


def test_unsupported_numbers_are_deduplicated_in_order():
    assert unsupported_numbers("It's $9, yes $9, until 5 PM.", [LUNCH]) == ["9", "5"]


def test_spelled_out_numbers_are_not_seen_by_the_check():
    # Known limit: this is why generation is told to write digits (decision log #23).
    assert unsupported_numbers("A backup lunch is nine dollars.", [LUNCH]) == []


def test_answer_without_numbers_changes_nothing():
    assert check(["backup lunch for $6"], [LUNCH], answer="Yes, we can help with lunch!").score == 1.0
