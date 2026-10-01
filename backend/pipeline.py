"""The answer pipeline, steps 1-8 from docs/CLAUDE.md. Every question is logged, whatever happens.

retrieve -> out-of-scope short-circuit -> classify sensitivity -> generate + claimed facts
-> mechanical adherence -> combine confidence -> sensitive / threshold -> log
"""

from backend import adherence, config, db, generation, retrieval, sensitivity
from backend.gemini import GeminiError
from backend.schemas import AskResponse, Source
from backend.urgency import is_urgent


def answer_question(question: str) -> AskResponse:
    log: dict = {"question": question, "is_urgent": is_urgent(question), "escalated": True}
    sources: list[Source] = []

    try:
        # 1. Retrieve
        hits = retrieval.retrieve(question)
        log["semantic_score"] = retrieval.semantic_score(hits[0].cosine) if hits else 0.0

        # 2. Out-of-scope short-circuit: no LLM calls
        if retrieval.is_out_of_scope(hits):
            log["escalation_reason"] = "out_of_scope"
        else:
            context = retrieval.relevant(hits)  # what the model sees AND what facts are checked against
            log["retrieved_chunk_ids"] = [c.id for c in context]

            # 3. Sensitivity
            sens = sensitivity.classify(question)
            sensitive = sensitivity.is_sensitive(sens)
            log.update(
                is_sensitive=sensitive,
                sensitivity_category=sens.category.value,
                sensitivity_score=sens.score,
                sensitivity_rationale=sens.rationale,
            )

            # 4. Generate (runs even when sensitive, so the operator sees the would-have-been answer)
            gen = generation.generate(question, context)

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
    return AskResponse(log_id=log_id, escalated=True, answer=None, message=config.ESCALATION_MESSAGE, sources=[])
