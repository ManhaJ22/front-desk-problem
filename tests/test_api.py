"""HTTP layer. Response key sets are copied from frontend/src/mockApi.js, which the
frontend was built and verified against; any drift between the two fails here."""

import json

import pytest
from fastapi.testclient import TestClient

from backend import config, db, gemini, main, retrieval
from backend.retrieval import RetrievedChunk
from backend.schemas import GeneratedAnswer, SensitivityCategory, SensitivityResult

ASK_KEYS = {"log_id", "escalated", "answer", "message", "sources"}
QUESTION_KEYS = {
    "id", "created_at", "question", "answer", "escalated", "escalation_reason", "is_sensitive",
    "is_urgent", "sensitivity_category", "sensitivity_score", "sensitivity_rationale",
    "semantic_score", "adherence_score", "combined_score", "threshold_used",
    "retrieved_chunk_ids", "claimed_facts", "unmatched_facts", "answer_shown", "resolved", "priority",
}  # fmt: skip
CHUNK_KEYS = {"id", "category", "title", "content", "source", "updated_at"}
STATS_KEYS = {"total", "answered", "escalated", "unresolved", "by_reason"}
REASONS = {"out_of_scope", "sensitive_forced", "below_threshold", "partial_answer", "system_error"}

HOLIDAYS = RetrievedChunk("holidays", "Holiday Closures", "Little Acorns is OPEN on Veterans Day.", 0.9)


def handbook_size() -> int:
    with open(config.HANDBOOK_PATH, encoding="utf-8") as f:
        return len(json.load(f))


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(config, "SIMILARITY_FLOOR", 0.5)
    monkeypatch.setattr(config, "SEMANTIC_ZERO", 0.5)
    monkeypatch.setattr(config, "SIMILARITY_CEILING", 0.8)
    with TestClient(main.app) as c:  # runs startup: init_db + seed (fake embedder)
        yield c


@pytest.fixture
def answered(monkeypatch, fake_generate):
    """Make the next /api/ask produce a grounded, routine answer."""
    monkeypatch.setattr(retrieval, "retrieve", lambda q: [HOLIDAYS])
    fake_generate.responses[SensitivityResult] = SensitivityResult(category=SensitivityCategory.none, score=1, rationale="r")
    fake_generate.responses[GeneratedAnswer] = GeneratedAnswer(answer="Yes, we're open!", claimed_facts=["OPEN on Veterans Day"])


def escalate_one(question: str = "Do you offer swim lessons?") -> int:
    return db.insert_log({"question": question, "escalated": True, "escalation_reason": "out_of_scope"})


# --- startup ---------------------------------------------------------------------------------


def test_startup_seeds_handbook_and_health_ok(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True and body["db_path"].endswith("test.db")
    assert len(client.get("/api/operator/kb").json()) == handbook_size()


def test_startup_fails_fast_without_api_key(monkeypatch):
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        with TestClient(main.app):
            pass


# --- /api/ask ---------------------------------------------------------------------------------


def test_ask_answered_shape(client, answered):
    body = client.post("/api/ask", json={"question": "Are you open on Veterans Day?"}).json()
    assert set(body) == ASK_KEYS
    assert body["escalated"] is False
    assert body["answer"] == "Yes, we're open!" and body["message"] is None
    assert body["sources"] == [{"id": "holidays", "title": "Holiday Closures"}]


def test_ask_escalated_shape_shows_only_message(client, monkeypatch, fake_generate):
    monkeypatch.setattr(retrieval, "retrieve", lambda q: [])
    fake_generate.responses[SensitivityResult] = SensitivityResult(category=SensitivityCategory.none, score=1, rationale="r")
    body = client.post("/api/ask", json={"question": "Do you offer swim lessons?"}).json()
    assert set(body) == ASK_KEYS
    assert body == {**body, "escalated": True, "answer": None, "message": config.ESCALATION_MESSAGE, "sources": []}


@pytest.mark.parametrize("question", ["", "   ", "x" * 501])
def test_ask_rejects_empty_and_too_long(client, question):
    assert client.post("/api/ask", json={"question": question}).status_code == 422


def test_ask_trims_whitespace(client, answered):
    client.post("/api/ask", json={"question": "  Are you open?  "})
    assert db.list_logs("all")[0]["question"] == "Are you open?"


# --- questions --------------------------------------------------------------------------------


def test_questions_needs_review_vs_all_and_shape(client, answered):
    client.post("/api/ask", json={"question": "Are you open on Veterans Day?"})  # answered
    esc = escalate_one()
    needs = client.get("/api/operator/questions").json()
    assert [q["id"] for q in needs] == [esc]
    assert set(needs[0]) == QUESTION_KEYS
    assert needs[0]["priority"] == 4
    assert len(client.get("/api/operator/questions?view=all").json()) == 2
    assert client.get("/api/operator/questions?view=bogus").status_code == 422


def test_questions_are_sorted_by_triage_priority(client):
    plain = escalate_one("plain")
    urgent = db.insert_log({"question": "urgent", "escalated": True, "is_urgent": True})
    both = db.insert_log({"question": "both", "escalated": True, "is_urgent": True, "is_sensitive": True})
    sensitive = db.insert_log({"question": "sensitive", "escalated": True, "is_sensitive": True})
    ids = [q["id"] for q in client.get("/api/operator/questions").json()]
    assert ids == [both, urgent, sensitive, plain]


def test_resolve(client):
    esc = escalate_one()
    body = client.post(f"/api/operator/questions/{esc}/resolve").json()
    assert set(body) == QUESTION_KEYS and body["resolved"] is True
    assert client.get("/api/operator/questions").json() == []
    assert client.post("/api/operator/questions/9999/resolve").status_code == 404


def test_add_to_kb_creates_chunk_and_resolves(client):
    esc = escalate_one()
    body = client.post(
        f"/api/operator/questions/{esc}/add-to-kb",
        json={"category": "faq", "title": "Do you offer swim lessons?", "content": "No, we don't offer swim lessons."},
    ).json()
    assert set(body) == {"chunk", "question"}
    assert set(body["chunk"]) == CHUNK_KEYS and set(body["question"]) == QUESTION_KEYS
    assert body["question"]["resolved"] is True
    kb_ids = [c["id"] for c in client.get("/api/operator/kb").json()]
    assert body["chunk"]["id"] in kb_ids


def test_add_to_kb_validation_and_404(client):
    esc = escalate_one()
    good = {"category": "faq", "title": "T", "content": "C"}
    assert client.post("/api/operator/questions/9999/add-to-kb", json=good).status_code == 404
    assert client.post(f"/api/operator/questions/{esc}/add-to-kb", json={**good, "category": "nope"}).status_code == 422
    assert client.post(f"/api/operator/questions/{esc}/add-to-kb", json={**good, "content": "  "}).status_code == 422


def test_add_to_kb_when_gemini_down_is_503_and_leaves_question_open(client, monkeypatch):
    esc = escalate_one()

    def down(texts, task_type):
        raise gemini.GeminiError("quota")

    monkeypatch.setattr(gemini, "embed", down)
    res = client.post(f"/api/operator/questions/{esc}/add-to-kb", json={"category": "faq", "title": "T", "content": "C"})
    assert res.status_code == 503
    assert db.get_log(esc)["resolved"] is False


# --- knowledge base ------------------------------------------------------------------------------


def test_kb_crud(client):
    listing = client.get("/api/operator/kb").json()
    assert all(set(c) == CHUNK_KEYS for c in listing)  # never exposes embeddings

    created = client.post("/api/operator/kb", json={"category": "faq", "title": "Parking", "content": "Street only."})
    assert created.status_code == 201 and set(created.json()) == CHUNK_KEYS
    chunk_id = created.json()["id"]

    updated = client.put(f"/api/operator/kb/{chunk_id}", json={"category": "general", "title": "Parking", "content": "10-car lot."})
    assert updated.json()["content"] == "10-car lot." and updated.json()["category"] == "general"
    assert client.put("/api/operator/kb/nope", json={"category": "faq", "title": "T", "content": "C"}).status_code == 404

    assert client.delete(f"/api/operator/kb/{chunk_id}").status_code == 204
    assert client.delete(f"/api/operator/kb/{chunk_id}").status_code == 404
    assert len(client.get("/api/operator/kb").json()) == len(listing)


# --- stats ----------------------------------------------------------------------------------------


def test_stats(client, answered):
    client.post("/api/ask", json={"question": "Are you open on Veterans Day?"})
    esc = escalate_one()
    db.insert_log({"question": "x", "escalated": True, "escalation_reason": "sensitive_forced"})
    db.mark_resolved(esc)
    body = client.get("/api/operator/stats").json()
    assert set(body) == STATS_KEYS and set(body["by_reason"]) == REASONS
    assert body["total"] == 3 and body["answered"] == 1 and body["escalated"] == 2 and body["unresolved"] == 1
    assert body["by_reason"]["out_of_scope"] == 1 and body["by_reason"]["sensitive_forced"] == 1


# --- frontend serving --------------------------------------------------------------------------------


@pytest.fixture
def built_frontend(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    monkeypatch.setattr(main, "FRONTEND_DIST", dist)
    return dist


def test_spa_routes_serve_index_and_assets(client, built_frontend):
    assert client.get("/").text == "<html>app</html>"
    assert client.get("/operator").text == "<html>app</html>"  # client-side route
    assert client.get("/assets/app.js").text == "console.log(1)"


def test_unknown_api_route_is_json_404_not_index(client, built_frontend):
    res = client.get("/api/nope")
    assert res.status_code == 404 and res.json() == {"detail": "Not found"}


def test_path_traversal_falls_back_to_index(client, built_frontend):
    (built_frontend.parent / "secret.txt").write_text("secret")
    assert "secret" not in client.get("/..%2Fsecret.txt").text
