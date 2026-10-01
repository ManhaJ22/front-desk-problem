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

            # 7. Sensitive always escalates; otherwise the confidence bar decides
            if sensitive:
                log["escalation_reason"] = "sensitive_forced"
            elif combined < config.CONFIDENCE_THRESHOLD:
                log["escalation_reason"] = "below_threshold"
            else:
                log["escalated"] = False
                backing = {chunk_id for _, chunk_id in adh.matched}
                sources = [Source(id=c.id, title=c.title) for c in context if c.id in backing]

    except GeminiError:
        log["escalation_reason"] = "system_error"

    # 8. Log everything
    log_id = db.insert_log(log)

    if log["escalated"]:
        return AskResponse(log_id=log_id, escalated=True, answer=None, message=config.ESCALATION_MESSAGE, sources=[])
    return AskResponse(log_id=log_id, escalated=False, answer=log["answer"], message=None, sources=sources)
