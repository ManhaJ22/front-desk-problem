import pytest

from backend import config, kb, retrieval
from backend.retrieval import RetrievedChunk, cosine, is_out_of_scope, relevant, retrieve, semantic_score
from backend.seed import seed_if_empty


def hit(cos: float, id: str = "x") -> RetrievedChunk:
    return RetrievedChunk(id, id.title(), "content", cos)


# --- cosine -----------------------------------------------------------------------------


def test_cosine_basics():
    assert cosine([1, 0], [2, 0]) == pytest.approx(1.0)
    assert cosine([1, 0], [0, 3]) == pytest.approx(0.0)
    assert cosine([1, 0], [-1, 0]) == pytest.approx(-1.0)
    assert cosine([0, 0], [1, 0]) == 0.0  # zero vector doesn't divide by zero


# --- retrieve (fake bag-of-words embedder, see conftest) ------------------------------------


# Ranking is tested on chunks with clearly separated vocabulary, so the test checks
# retrieve()'s logic rather than the crude fake embedder's quality. Real retrieval
# quality on the handbook is measured with real embeddings by calibrate_embeddings.py.
@pytest.mark.parametrize(
    "question, expected_top",
    [
        ("Are you open on Veterans Day?", "veterans-day"),
        ("How much is infant tuition?", "infant-tuition"),
        ("Is there a swim program?", "swim-program"),
    ],
)
def test_retrieve_ranks_the_closest_chunk_first(question, expected_top):
    kb.create_chunk("calendar", "Veterans Day", "The center is open on Veterans Day.")
    kb.create_chunk("tuition", "Infant tuition", "Infant tuition is $2,150 per month.")
    kb.create_chunk("faq", "Swim program", "There is no swim program.")
    assert retrieve(question)[0].id == expected_top


def test_retrieve_returns_top_k_sorted_and_embeds_as_query(fake_embed):
    seed_if_empty()
    hits = retrieve("What is the late pick-up fee?")
    assert len(hits) == config.TOP_K
    assert [h.cosine for h in hits] == sorted((h.cosine for h in hits), reverse=True)
    assert fake_embed.calls[-1] == (["What is the late pick-up fee?"], "RETRIEVAL_QUERY")


def test_retrieve_on_empty_kb_returns_nothing():
    assert retrieve("anything") == []


# --- scope / relevance / semantic score -------------------------------------------------------


def test_out_of_scope_boundary(monkeypatch):
    monkeypatch.setattr(config, "SIMILARITY_FLOOR", 0.5)
    assert is_out_of_scope([hit(0.49)])
    assert not is_out_of_scope([hit(0.50)])
    assert is_out_of_scope([])


def test_relevant_filters_at_floor(monkeypatch):
    monkeypatch.setattr(config, "SIMILARITY_FLOOR", 0.5)
    hits = [hit(0.9, "a"), hit(0.5, "b"), hit(0.4, "c")]
    assert [h.id for h in relevant(hits)] == ["a", "b"]


def test_semantic_score_maps_from_zero_anchor_to_ceiling(monkeypatch):
    monkeypatch.setattr(config, "SEMANTIC_ZERO", 0.5)
    monkeypatch.setattr(config, "SIMILARITY_CEILING", 0.8)
    assert semantic_score(0.4) == 0.0
    assert semantic_score(0.5) == 0.0
    assert semantic_score(0.65) == pytest.approx(0.5)
    assert semantic_score(0.8) == 1.0
    assert semantic_score(0.95) == 1.0


def test_semantic_scale_is_independent_of_the_floor(monkeypatch):
    # Regression for decision log #21: a question just above the floor must not score ~0.
    monkeypatch.setattr(config, "SIMILARITY_FLOOR", 0.64)
    monkeypatch.setattr(config, "SEMANTIC_ZERO", 0.50)
    monkeypatch.setattr(config, "SIMILARITY_CEILING", 0.77)
    assert semantic_score(0.663) == pytest.approx(0.6037, abs=1e-3)


def test_calibrated_config_answers_weakest_on_topic_question_when_facts_verify():
    # With the shipped config, the weakest calibrated on-topic match (Veterans Day, 0.663)
    # clears the bar if every claimed fact is verified (adherence 1.0).
    combined = config.SEMANTIC_WEIGHT * semantic_score(0.663) + config.ADHERENCE_WEIGHT * 1.0
    assert 0.663 >= config.SIMILARITY_FLOOR
    assert combined >= config.CONFIDENCE_THRESHOLD


def test_module_reads_config_at_call_time(monkeypatch):
    # Calibration edits config values; retrieval must not cache them at import.
    monkeypatch.setattr(config, "SIMILARITY_FLOOR", 0.99)
    assert retrieval.is_out_of_scope([hit(0.9)])
