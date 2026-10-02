"""The answer pipeline, steps 0-8 from docs/CLAUDE.md. Every question is logged, whatever happens.

small talk -> classify (sensitivity + urgency + standalone rewrite, sees the conversation) -> retrieve
-> out-of-scope short-circuit -> generate + claimed facts -> mechanical adherence -> combine confidence
-> sensitive / threshold -> log
"""

from backend import adherence, config, db, generation, retrieval, sensitivity
from backend.gemini import GeminiError
from backend.schemas import AskResponse, SensitivityResult, Source
from backend.small_talk import small_talk_reply
from backend.urgency import is_urgent


def _record_sensitivity(log: dict, sens: SensitivityResult) -> bool:
    """Store the classifier's sensitivity AND urgency judgement (urgency replaces the keyword guess, #44)."""
    sensitive = sensitivity.is_sensitive(sens)
    log.update(
        is_urgent=sens.is_urgent,
        urgency_reason=sens.urgency_reason or None,
        is_sensitive=sensitive,
        sensitivity_category=sens.category.value,
        sensitivity_score=sens.score,
        sensitivity_rationale=sens.rationale,
    )
    return sensitive


def answer_question(question: str, history: list[dict] | None = None) -> AskResponse:
    """`history`: prior chat turns [{role, text}] sent by the parent page (decision log #45)."""
    history = history or []

    # 0. Small talk ("hi", "thanks!") gets a canned reply: no retrieval, no LLM, no staff (decision log #40).
    reply = small_talk_reply(question)
    if reply is not None:
        log_id = db.insert_log(
            {"question": question, "history": history, "answer": reply, "escalated": False, "answer_shown": True}
        )
        return AskResponse(log_id=log_id, escalated=False, answer=reply, message=None, sources=[])

    # Keyword urgency is only the fallback; the classifier's judgement replaces it when it runs (#44).
    log: dict = {"question": question, "history": history, "is_urgent": is_urgent(question), "escalated": True}
    sources: list[Source] = []

    try:
        # 1. Classify first: sensitivity, urgency, and the standalone rewrite of a follow-up (#45).
        #    A failure here isn't fatal yet: retrieval can still run on the original question.
        try:
            sens = sensitivity.classify(question, history)
        except GeminiError:
            sens = None
        sensitive = _record_sensitivity(log, sens) if sens else False
        standalone = sens.standalone_question.strip() if sens else question
        if standalone != question:
            log["standalone_question"] = standalone

        # 2. Retrieve on the standalone question
        hits = retrieval.retrieve(standalone)
        log["semantic_score"] = retrieval.semantic_score(hits[0].cosine) if hits else 0.0

        # 3. Out-of-scope short-circuit: no generation (nothing to ground an answer in); the
        #    sensitivity/urgency from step 1 still drive triage, e.g. a bullying question (#38).
        if retrieval.is_out_of_scope(hits):
            log["escalation_reason"] = "out_of_scope"
        else:
            context = retrieval.relevant(hits)  # what the model sees AND what facts are checked against
            log["retrieved_chunk_ids"] = [c.id for c in context]
            if sens is None:
                raise GeminiError("classification failed for an in-scope question")  # sensitivity unknown

            # 4. Generate (runs even when sensitive, so the operator sees the would-have-been answer)
            gen = generation.generate(standalone, context, history)

            # 5. Mechanical adherence: claimed facts + every number in the answer text
            adh = adherence.check(gen.claimed_facts, context, answer=gen.answer)

            # 6. Combine
            combined = config.SEMANTIC_WEIGHT * log["semantic_score"] + config.ADHERENCE_WEIGHT * adh.score
            log.update(
                answer=gen.answer,
                claimed_facts=gen.claimed_facts,
                unmatched_facts=adh.unmatched,
                adherence_score=adh.score,
                combined_score=combined,
                threshold_used=config.CONFIDENCE_THRESHOLD,
            )

            # 7. Sensitive escalates unless staff already answered it in the KB (decision log #28):
            #    every claimed fact AND every number in the answer is supported by staff-written chunks.
            staff_chunks = [c for c in context if c.source == "staff"]
            staff_backed = (
                bool(staff_chunks)
                and bool(gen.claimed_facts)
                and not adh.unmatched
                and all(
                    any(adherence.fact_matches(f, f"{c.title}\n{c.content}") for c in staff_chunks)
                    for f in gen.claimed_facts
                )
                and not adherence.unsupported_numbers(gen.answer, staff_chunks)
            )
            # A fully verified answer: every claimed fact and answer number checks out, bar cleared.
            verified = bool(gen.claimed_facts) and not adh.unmatched and combined >= config.CONFIDENCE_THRESHOLD

            if sensitive and not (staff_backed and verified):
                log["escalation_reason"] = "sensitive_forced"
                # Show a verified answer AND notify staff (decision log #37); never an unverified one.
                log["answer_shown"] = verified
            elif not verified:
                log["escalation_reason"] = "below_threshold"
            elif not gen.fully_answers_question:
                # Verified answer to the part the handbook covers; staff fill the gap (decision log #42).
                log["escalation_reason"] = "partial_answer"
                log["answer_shown"] = True
            else:
                log["escalated"] = False
                log["answer_shown"] = True

            if log.get("answer_shown"):
                backing = {chunk_id for _, chunk_id in adh.matched}
                sources = [Source(id=c.id, title=c.title) for c in context if c.id in backing]

    except GeminiError:
        log["escalation_reason"] = "system_error"

    # 8. Log everything
    log_id = db.insert_log(log)

    if not log["escalated"]:
        return AskResponse(log_id=log_id, escalated=False, answer=log["answer"], message=None, sources=sources)
    if log.get("answer_shown"):
        return AskResponse(
            log_id=log_id, escalated=True, answer=log["answer"], message=config.SENSITIVE_ANSWER_NOTE, sources=sources
        )
    # Message-only escalation; sensitive questions get a soft opener first (decision log #41).
    opener = config.SENSITIVITY_OPENERS.get(log.get("sensitivity_category"), "") if log.get("is_sensitive") else ""
    return AskResponse(log_id=log_id, escalated=True, answer=None, message=opener + config.ESCALATION_MESSAGE, sources=[])
