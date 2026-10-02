"""Pipeline orchestration. Retrieval hits are controlled directly; LLM calls are faked."""

import pytest

from backend import config, db, retrieval
from backend.gemini import GeminiError
from backend.pipeline import answer_question
from backend.retrieval import RetrievedChunk
from backend.schemas import GeneratedAnswer, SensitivityCategory, SensitivityResult

HOLIDAYS = RetrievedChunk(
    "holidays", "Holiday Closures", "Little Acorns is OPEN on Veterans Day, with normal hours of 7:00 AM to 6:00 PM.", 0.9
)
TUITION = RetrievedChunk("tuition", "Monthly Tuition", "Infants (6 weeks to 12 months) $2,150 per month.", 0.6)
FAR_AWAY = RetrievedChunk("naps", "Nap and Rest Time", "Rest time is from 12:30 PM to 2:30 PM.", 0.3)

ON_TOPIC_ANSWER = GeneratedAnswer(
    answer="Yes! We're open on Veterans Day, 7:00 AM to 6:00 PM.",
    claimed_facts=["OPEN on Veterans Day", "7:00 AM to 6:00 PM"],
)


@pytest.fixture(autouse=True)
def fixed_config(monkeypatch):
    # Simple numbers so expected scores are easy to compute by hand.
    monkeypatch.setattr(config, "SIMILARITY_FLOOR", 0.5)
    monkeypatch.setattr(config, "SEMANTIC_ZERO", 0.5)
    monkeypatch.setattr(config, "SIMILARITY_CEILING", 0.8)


@pytest.fixture
def hits(monkeypatch):
    """Set what retrieval returns: `hits([...])`."""

    def set_hits(chunks):
        monkeypatch.setattr(retrieval, "retrieve", lambda q: list(chunks))

    return set_hits


def sens(category=SensitivityCategory.none, score=1):
    return SensitivityResult(category=category, score=score, rationale="because")


def only_log_row() -> dict:
    rows = db.list_logs("all")
    assert len(rows) == 1, "every question writes exactly one log row"
    return rows[0]


# --- out of scope ------------------------------------------------------------------------


def test_out_of_scope_classifies_but_never_generates(hits, fake_generate):
    hits([FAR_AWAY])
    fake_generate.responses[SensitivityResult] = sens()
    res = answer_question("Do you offer swim lessons?")
    assert res.escalated and res.answer is None and res.message == config.ESCALATION_MESSAGE
    assert fake_generate.calls_for(SensitivityResult) == 1
    assert fake_generate.calls_for(GeneratedAnswer) == 0  # nothing to ground an answer in
    row = only_log_row()
    assert row["escalation_reason"] == "out_of_scope"
    assert row["sensitivity_category"] == "none" and row["is_sensitive"] is False
    assert row["semantic_score"] == 0.0
    assert row["retrieved_chunk_ids"] == []


def test_out_of_scope_sensitive_question_is_marked_sensitive(hits, fake_generate):
    # Decision log #38: "my child is being bullied, can we get counseling?" isn't in the handbook.
    hits([FAR_AWAY])
    fake_generate.responses[SensitivityResult] = sens(SensitivityCategory.emotional_social, 4)
    res = answer_question("my child is currently experiencing bullying, can we get counseling?")
    assert res.escalated and res.answer is None
    row = only_log_row()
    assert row["escalation_reason"] == "out_of_scope"  # why there's no answer
    assert row["is_sensitive"] is True and row["sensitivity_category"] == "emotional_social"  # how to triage


def test_out_of_scope_classification_failure_stays_out_of_scope(hits, fake_generate):
    hits([FAR_AWAY])
    fake_generate.responses[SensitivityResult] = GeminiError("429")
    assert answer_question("q").escalated
    row = only_log_row()
    assert row["escalation_reason"] == "out_of_scope"
    assert row["sensitivity_category"] is None


def test_empty_knowledge_base_is_out_of_scope(hits, fake_generate):
    hits([])
    fake_generate.responses[SensitivityResult] = sens()
    assert answer_question("Anything?").escalated
    assert only_log_row()["escalation_reason"] == "out_of_scope"
    assert fake_generate.calls_for(GeneratedAnswer) == 0


# --- answered ------------------------------------------------------------------------------


def test_grounded_routine_question_is_answered_with_sources(hits, fake_generate):
    hits([HOLIDAYS, TUITION, FAR_AWAY])
    fake_generate.responses[SensitivityResult] = sens()
    fake_generate.responses[GeneratedAnswer] = ON_TOPIC_ANSWER
    res = answer_question("Are you open on Veterans Day?")
    assert not res.escalated
    assert res.answer == ON_TOPIC_ANSWER.answer and res.message is None
    assert only_log_row()["answer_shown"] is True
    assert [s.id for s in res.sources] == ["holidays"]  # only chunks that backed a matched fact
    row = only_log_row()
    assert row["escalated"] is False and row["escalation_reason"] is None
    assert row["retrieved_chunk_ids"] == ["holidays", "tuition"]  # below-floor chunk excluded
    assert row["adherence_score"] == 1.0
    assert row["combined_score"] == pytest.approx(1.0)
    assert row["threshold_used"] == 0.80


def test_generation_and_adherence_see_only_relevant_chunks(hits, fake_generate):
    hits([HOLIDAYS, FAR_AWAY])
    fake_generate.responses[SensitivityResult] = sens()
    # A fact that only exists in the below-floor chunk must NOT count as supported.
    fake_generate.responses[GeneratedAnswer] = GeneratedAnswer(answer="...", claimed_facts=["Rest time is from 12:30 PM to 2:30 PM"])
    answer_question("When is nap time?")
    gen_prompt = next(p for p, _, s in fake_generate.calls if s is GeneratedAnswer)
    assert "Nap and Rest Time" not in gen_prompt
    assert only_log_row()["unmatched_facts"] == ["Rest time is from 12:30 PM to 2:30 PM"]


# --- sensitive always escalates (decision log #18) ------------------------------------------


@pytest.mark.parametrize("category", [c for c in SensitivityCategory if c is not SensitivityCategory.none])
def test_sensitive_verified_answer_is_shown_and_staff_notified(hits, fake_generate, category):
    # Decision log #37: escalate to staff AND show the parent the verified answer.
    hits([HOLIDAYS])
    fake_generate.responses[SensitivityResult] = sens(category, 3)
    fake_generate.responses[GeneratedAnswer] = ON_TOPIC_ANSWER
    res = answer_question("q")
    assert res.escalated
    assert res.answer == ON_TOPIC_ANSWER.answer
    assert res.message == config.SENSITIVE_ANSWER_NOTE
    assert [s.id for s in res.sources] == ["holidays"]
    row = only_log_row()
    assert row["escalation_reason"] == "sensitive_forced"
    assert row["is_sensitive"] is True and row["answer_shown"] is True
    assert db.list_logs("needs_review")  # still in the staff queue


def test_sensitive_unverified_answer_is_never_shown(hits, fake_generate):
    hits([HOLIDAYS])
    fake_generate.responses[SensitivityResult] = sens(SensitivityCategory.health, 5)
    fake_generate.responses[GeneratedAnswer] = GeneratedAnswer(
        answer="Yes, open until 8:00 PM.", claimed_facts=["OPEN on Veterans Day", "open until 8:00 PM"]
    )
    res = answer_question("q")
    assert res.escalated and res.answer is None and res.sources == []
    assert res.message == config.SENSITIVITY_OPENERS["health"] + config.ESCALATION_MESSAGE  # soft opener (#41)
    row = only_log_row()
    assert row["answer_shown"] is False
    assert row["answer"] == "Yes, open until 8:00 PM."  # still logged for the operator


def test_below_threshold_answer_is_never_shown(hits, fake_generate):
    hits([HOLIDAYS])
    fake_generate.responses[SensitivityResult] = sens()
    fake_generate.responses[GeneratedAnswer] = GeneratedAnswer(answer="Open until 8:00 PM.", claimed_facts=["open until 8:00 PM"])
    res = answer_question("q")
    assert res.escalated and res.answer is None and res.message == config.ESCALATION_MESSAGE
    assert only_log_row()["answer_shown"] is False


def test_low_scored_category_tag_is_answered_when_grounded(hits, fake_generate):
    # Decision log #25: "how do I call her in sick?" mentions health but is routine.
    hits([HOLIDAYS])
    fake_generate.responses[SensitivityResult] = sens(SensitivityCategory.health, 2)
    fake_generate.responses[GeneratedAnswer] = ON_TOPIC_ANSWER
    res = answer_question("q")
    assert not res.escalated
    row = only_log_row()
    assert row["is_sensitive"] is False and row["sensitivity_category"] == "health"


@pytest.mark.parametrize("score, escalated", [(3, False), (4, True)])
def test_category_none_escalates_from_score_4(hits, fake_generate, score, escalated):
    hits([HOLIDAYS])
    fake_generate.responses[SensitivityResult] = sens(SensitivityCategory.none, score)
    fake_generate.responses[GeneratedAnswer] = ON_TOPIC_ANSWER
    assert answer_question("q").escalated is escalated
    assert only_log_row()["is_sensitive"] is escalated


# --- confidence threshold ---------------------------------------------------------------------


def test_unsupported_facts_fall_below_threshold(hits, fake_generate):
    hits([HOLIDAYS])
    fake_generate.responses[SensitivityResult] = sens()
    fake_generate.responses[GeneratedAnswer] = GeneratedAnswer(
        answer="We're open until 8:00 PM on Veterans Day.", claimed_facts=["open until 8:00 PM"]
    )
    res = answer_question("How late are you open on Veterans Day?")
    assert res.escalated and res.answer is None
    row = only_log_row()
    assert row["escalation_reason"] == "below_threshold"
    # The listed fact fails AND the answer text's "8" is flagged by the answer-number check.
    assert row["unmatched_facts"] == ["open until 8:00 PM", 'Answer says "8", which isn\'t in the handbook']
    assert row["combined_score"] == pytest.approx(0.35)  # semantic 1.0 * 0.35 + adherence 0 * 0.65


def test_unlisted_wrong_number_in_answer_text_escalates(hits, fake_generate):
    # Decision log #23: the listed fact checks out, but the prose adds a time the handbook doesn't have.
    hits([HOLIDAYS])
    fake_generate.responses[SensitivityResult] = sens()
    fake_generate.responses[GeneratedAnswer] = GeneratedAnswer(
        answer="Yes, we're open on Veterans Day until 8:00 PM.", claimed_facts=["OPEN on Veterans Day"]
    )
    res = answer_question("Are you open on Veterans Day?")
    assert res.escalated
    row = only_log_row()
    assert row["escalation_reason"] == "below_threshold"
    assert row["adherence_score"] == 0.5
    assert row["unmatched_facts"] == ['Answer says "8", which isn\'t in the handbook']


def test_no_claimed_facts_escalates(hits, fake_generate):
    hits([HOLIDAYS])
    fake_generate.responses[SensitivityResult] = sens()
    fake_generate.responses[GeneratedAnswer] = GeneratedAnswer(answer="I'm not sure.", claimed_facts=[])
    assert answer_question("q").escalated
    assert only_log_row()["escalation_reason"] == "below_threshold"


def test_weak_retrieval_can_sink_a_fully_supported_answer(hits, fake_generate):
    # cosine 0.6 -> semantic (0.6-0.5)/0.3 = 0.33; combined = 0.117 + 0.65 = 0.77 < 0.80
    hits([RetrievedChunk(HOLIDAYS.id, HOLIDAYS.title, HOLIDAYS.content, 0.6)])
    fake_generate.responses[SensitivityResult] = sens()
    fake_generate.responses[GeneratedAnswer] = ON_TOPIC_ANSWER
    assert answer_question("q").escalated
    assert only_log_row()["escalation_reason"] == "below_threshold"


# --- errors and urgency ---------------------------------------------------------------------------


def test_gemini_error_during_classification_escalates_as_system_error(hits, fake_generate):
    hits([HOLIDAYS])
    fake_generate.responses[SensitivityResult] = GeminiError("429")
    res = answer_question("Are you open on Veterans Day?")
    assert res.escalated and res.message == config.ESCALATION_MESSAGE
    row = only_log_row()
    assert row["escalation_reason"] == "system_error"
    assert row["retrieved_chunk_ids"] == ["holidays"]  # what happened before the failure is kept


def test_gemini_error_during_retrieval_escalates_as_system_error(monkeypatch):
    def boom(q):
        raise GeminiError("embed failed")

    monkeypatch.setattr(retrieval, "retrieve", boom)
    assert answer_question("q").escalated
    assert only_log_row()["escalation_reason"] == "system_error"


def test_urgency_is_logged_on_every_path(hits, fake_generate):
    hits([FAR_AWAY])
    fake_generate.responses[SensitivityResult] = sens()
    answer_question("Can I pick up early today?")
    assert only_log_row()["is_urgent"] is True


# --- staff-written answers win over the sensitivity rule (decision log #28) --------------------

STAFF_SICK = RetrievedChunk(
    "sick-child", "Sick child", "If your child is sick, call us at (555) 014-2200 and keep them home.", 0.9, "staff"
)
SEEDED_ILLNESS = RetrievedChunk(
    "illness", "Illness Policy", "Children must be fever-free for 24 hours before returning.", 0.85, "handbook"
)


def sick_question(fake_generate, answer, facts):
    fake_generate.responses[SensitivityResult] = sens(SensitivityCategory.health, 4)
    fake_generate.responses[GeneratedAnswer] = GeneratedAnswer(answer=answer, claimed_facts=facts)
    return answer_question("my child is sick, what do I do?")


def test_sensitive_question_fully_backed_by_staff_entry_is_answered(hits, fake_generate):
    hits([STAFF_SICK, SEEDED_ILLNESS])
    res = sick_question(fake_generate, "Please call us at (555) 014-2200 and keep them home.", ["call us at (555) 014-2200", "keep them home"])
    assert not res.escalated
    row = only_log_row()
    assert row["is_sensitive"] is True and row["escalation_reason"] is None


def test_sensitive_question_backed_by_seeded_handbook_still_escalates(hits, fake_generate):
    hits([SEEDED_ILLNESS])
    res = sick_question(fake_generate, "They must be fever-free for 24 hours.", ["fever-free for 24 hours before returning"])
    assert res.escalated
    assert res.message == config.SENSITIVE_ANSWER_NOTE  # verified handbook answer shown + staff notified (#37)
    assert only_log_row()["escalation_reason"] == "sensitive_forced"


def test_sensitive_answer_mixing_staff_and_seeded_facts_escalates(hits, fake_generate):
    hits([STAFF_SICK, SEEDED_ILLNESS])
    res = sick_question(
        fake_generate,
        "Call us at (555) 014-2200; they must be fever-free for 24 hours.",
        ["call us at (555) 014-2200", "fever-free for 24 hours before returning"],
    )
    assert res.escalated
    assert only_log_row()["escalation_reason"] == "sensitive_forced"


def test_sensitive_staff_answer_with_unsupported_number_escalates(hits, fake_generate):
    hits([STAFF_SICK])
    res = sick_question(fake_generate, "Call us at (555) 014-2200 within 2 hours.", ["call us at (555) 014-2200"])
    assert res.escalated


# --- small talk (#40) and soft openers (#41) ---------------------------------------------------


def test_greeting_skips_the_pipeline_and_is_logged(hits, fake_generate, fake_embed):
    hits([HOLIDAYS])
    res = answer_question("Hello!")
    assert not res.escalated and res.answer == config.GREETING_RESPONSE and res.sources == []
    assert fake_generate.calls == [] and fake_embed.calls == []  # no retrieval, no LLM
    row = only_log_row()
    assert row["escalated"] is False and row["answer"] == config.GREETING_RESPONSE


def test_greeting_plus_question_runs_the_pipeline(hits, fake_generate):
    hits([HOLIDAYS])
    fake_generate.responses[SensitivityResult] = sens()
    fake_generate.responses[GeneratedAnswer] = ON_TOPIC_ANSWER
    res = answer_question("Hi! Are you open on Veterans Day?")
    assert res.answer == ON_TOPIC_ANSWER.answer


@pytest.mark.parametrize(
    "category, opener",
    [
        (SensitivityCategory.emotional_social, "I'm sorry to hear that — that sounds hard. "),
        (SensitivityCategory.health, "I'm sorry to hear your little one isn't feeling well. "),
        (SensitivityCategory.safety, ""),
        (SensitivityCategory.custody_legal, ""),
    ],
)
def test_sensitive_message_only_escalation_gets_category_opener(hits, fake_generate, category, opener):
    hits([FAR_AWAY])  # out of scope -> no answer to show
    fake_generate.responses[SensitivityResult] = sens(category, 5)
    res = answer_question("q")
    assert res.message == opener + config.ESCALATION_MESSAGE


def test_non_sensitive_escalation_has_no_opener(hits, fake_generate):
    hits([FAR_AWAY])
    fake_generate.responses[SensitivityResult] = sens()
    assert answer_question("Do you offer swim lessons?").message == config.ESCALATION_MESSAGE


def test_verified_sensitive_answer_gets_no_extra_opener(hits, fake_generate):
    # The generation prompt adds its own acknowledgment (#39); the staff note stays plain (#37).
    hits([HOLIDAYS])
    fake_generate.responses[SensitivityResult] = sens(SensitivityCategory.health, 4)
    fake_generate.responses[GeneratedAnswer] = ON_TOPIC_ANSWER
    res = answer_question("q")
    assert res.message == config.SENSITIVE_ANSWER_NOTE


# --- handbook gaps: share the related policy, escalate the gap (#42) ---------------------------


def test_verified_partial_answer_is_shown_and_escalated_as_handbook_gap(hits, fake_generate):
    hits([HOLIDAYS])
    fake_generate.responses[SensitivityResult] = sens()
    fake_generate.responses[GeneratedAnswer] = GeneratedAnswer(
        answer="We're open on Veterans Day, 7:00 AM to 6:00 PM. Our handbook doesn't cover the parade.",
        claimed_facts=["OPEN on Veterans Day", "7:00 AM to 6:00 PM"],
        fully_answers_question=False,
    )
    res = answer_question("Are you open on Veterans Day, and will you join the parade?")
    assert res.escalated and res.answer and res.message == config.SENSITIVE_ANSWER_NOTE
    assert [s.id for s in res.sources] == ["holidays"]
    row = only_log_row()
    assert row["escalation_reason"] == "partial_answer" and row["answer_shown"] is True
    assert db.list_logs("needs_review")  # the gap reaches the staff queue


def test_unverified_partial_answer_is_not_shown(hits, fake_generate):
    hits([HOLIDAYS])
    fake_generate.responses[SensitivityResult] = sens()
    fake_generate.responses[GeneratedAnswer] = GeneratedAnswer(
        answer="Open until 8:00 PM.", claimed_facts=["open until 8:00 PM"], fully_answers_question=False
    )
    res = answer_question("q")
    assert res.answer is None
    assert only_log_row()["escalation_reason"] == "below_threshold"
