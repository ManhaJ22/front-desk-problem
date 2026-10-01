"""Data layer: db.py, seed.py, kb.py."""

import json

import pytest

from backend import config, db, kb
from backend.seed import seed_if_empty
from tests.conftest import fake_vector


def handbook() -> list[dict]:
    with open(config.HANDBOOK_PATH, encoding="utf-8") as f:
        return json.load(f)


# --- db.init_db -------------------------------------------------------------------------


def test_init_db_is_idempotent():
    db.init_db()
    db.init_db()
    assert db.count_chunks() == 0


# --- seed ---------------------------------------------------------------------------------


def test_seed_inserts_every_handbook_chunk_in_one_embed_call(fake_embed):
    expected = handbook()
    assert seed_if_empty() == len(expected)
    assert db.count_chunks() == len(expected)
    assert len(fake_embed.calls) == 1
    texts, task_type = fake_embed.calls[0]
    assert task_type == "RETRIEVAL_DOCUMENT"
    assert texts[0] == kb.embedding_text(expected[0]["title"], expected[0]["content"])


def test_seed_is_noop_when_table_has_data(fake_embed):
    seed_if_empty()
    assert seed_if_empty() == 0
    assert len(fake_embed.calls) == 1


def test_seeded_embedding_matches_title_plus_content():
    seed_if_empty()
    first = handbook()[0]
    stored = next(c for c in db.list_chunks(with_embedding=True) if c["id"] == first["id"])
    assert stored["embedding"] == fake_vector(kb.embedding_text(first["title"], first["content"]))


# --- kb.create / update / delete ----------------------------------------------------------


def test_create_chunk_slugs_title_and_embeds(fake_embed):
    chunk = kb.create_chunk("faq", "Do you offer swim lessons?", "No, we don't offer swim lessons.")
    assert chunk["id"] == "do-you-offer-swim-lessons"
    assert chunk["category"] == "faq"
    assert "embedding" not in chunk
    assert fake_embed.calls[-1] == (
        [kb.embedding_text("Do you offer swim lessons?", "No, we don't offer swim lessons.")],
        "RETRIEVAL_DOCUMENT",
    )


def test_create_chunk_deduplicates_ids():
    ids = [kb.create_chunk("faq", "Parking", f"Version {n}")["id"] for n in range(3)]
    assert ids == ["parking", "parking-2", "parking-3"]


def test_update_chunk_reembeds_and_bumps_updated_at(fake_embed, monkeypatch):
    chunk = kb.create_chunk("faq", "Parking", "Street parking only.")
    monkeypatch.setattr(db, "now_iso", lambda: "2099-01-01T00:00:00+00:00")
    updated = kb.update_chunk(chunk["id"], "general", "Parking", "We have a 10-car lot.")
    assert updated["id"] == chunk["id"]
    assert updated["category"] == "general"
    assert updated["content"] == "We have a 10-car lot."
    assert updated["updated_at"] == "2099-01-01T00:00:00+00:00"
    assert fake_embed.calls[-1][0] == [kb.embedding_text("Parking", "We have a 10-car lot.")]
    stored = next(c for c in db.list_chunks(with_embedding=True) if c["id"] == chunk["id"])
    assert stored["embedding"] == fake_vector(kb.embedding_text("Parking", "We have a 10-car lot."))


def test_update_missing_chunk_returns_none_without_embedding(fake_embed):
    assert kb.update_chunk("nope", "faq", "T", "C") is None
    assert fake_embed.calls == []


def test_delete_chunk():
    chunk = kb.create_chunk("faq", "Parking", "Street parking only.")
    assert kb.delete_chunk(chunk["id"]) is True
    assert kb.delete_chunk(chunk["id"]) is False
    assert db.get_chunk(chunk["id"]) is None


def test_failed_embed_writes_nothing(monkeypatch):
    from backend import gemini

    def boom(texts, task_type):
        raise gemini.GeminiError("quota")

    monkeypatch.setattr(gemini, "embed", boom)
    with pytest.raises(gemini.GeminiError):
        kb.create_chunk("faq", "Parking", "Street parking only.")
    assert db.count_chunks() == 0


def test_chunk_listing_hides_embeddings():
    kb.create_chunk("faq", "Parking", "Street parking only.")
    assert all("embedding" not in c for c in db.list_chunks())


# --- question_log ---------------------------------------------------------------------------


def test_log_round_trips_json_and_booleans():
    log_id = db.insert_log(
        {
            "question": "Are you open on Veterans Day?",
            "answer": "Yes.",
            "escalated": False,
            "is_urgent": True,
            "retrieved_chunk_ids": ["holidays"],
            "claimed_facts": ["OPEN on Veterans Day"],
        }
    )
    row = db.get_log(log_id)
    assert row["retrieved_chunk_ids"] == ["holidays"]
    assert row["claimed_facts"] == ["OPEN on Veterans Day"]
    assert row["unmatched_facts"] == []
    assert row["escalated"] is False
    assert row["is_urgent"] is True
    assert row["resolved"] is False
    assert row["created_at"]


def test_list_logs_needs_review_filters_escalated_unresolved():
    answered = db.insert_log({"question": "a", "escalated": False})
    open_esc = db.insert_log({"question": "b", "escalated": True, "escalation_reason": "out_of_scope"})
    done_esc = db.insert_log({"question": "c", "escalated": True, "escalation_reason": "out_of_scope"})
    db.mark_resolved(done_esc)
    assert [r["id"] for r in db.list_logs("needs_review")] == [open_esc]
    assert {r["id"] for r in db.list_logs("all")} == {answered, open_esc, done_esc}


def test_mark_resolved_returns_updated_row():
    log_id = db.insert_log({"question": "b", "escalated": True})
    assert db.mark_resolved(log_id)["resolved"] is True
    assert db.mark_resolved(9999) is None
