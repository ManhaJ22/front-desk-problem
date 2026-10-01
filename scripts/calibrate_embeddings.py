"""Suggest SIMILARITY_FLOOR / SIMILARITY_CEILING for the configured embedding model.

Embeds data/handbook.json plus hand-written on-topic and off-topic questions with the
REAL embedding model (2 API calls), prints each question's best-match cosine, and suggests:
  floor   = midpoint between the highest off-topic and lowest on-topic score
  ceiling = 90th percentile of on-topic scores
It only prints. A human copies the values into backend/config.py and logs them in
docs/decision-log.md.

Run: python scripts/calibrate_embeddings.py
"""

import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend import config, gemini  # noqa: E402
from backend.kb import embedding_text  # noqa: E402
from backend.retrieval import cosine  # noqa: E402

# Questions the handbook DOES answer (or at least covers the topic of).
ON_TOPIC = [
    "Are you open on Veterans Day?",
    "What is the tuition for infants?",
    "My child has a fever, can they come in?",
    "I forgot to pack lunch. Can you provide lunch today and what is it?",
    "How can I schedule a tour?",
    "What time do you close?",
    "How much is the late pickup fee?",
    "Do you close for snow days?",
    "Is there a sibling discount?",
    "Can my child bring peanut butter?",
    "Who is allowed to pick up my daughter?",
    "What should I pack for my toddler?",
    "When is nap time?",
    "Do kids need to be potty trained for preschool?",
    "My son bit another child, what happens now?",
    "Can staff give my child medicine?",
    "What are the teacher to child ratios?",
]

# Plausible daycare-parent questions the handbook does NOT cover, plus a few unrelated ones.
OFF_TOPIC = [
    "Do you offer swim lessons?",
    "Is there a summer camp program?",
    "Do you provide bus transportation from school?",
    "Can my child take piano lessons at the center?",
    "Do you have a spanish immersion program?",
    "What's the weather going to be tomorrow?",
    "How do I file my taxes?",
    "Can you recommend a good pediatric dentist?",
    "What's a good recipe for banana bread?",
    "Who won the football game last night?",
]


def main() -> None:
    if not config.GEMINI_API_KEY:
        sys.exit("GEMINI_API_KEY is not set (.env)")
    with open(config.HANDBOOK_PATH, encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Embedding model: {config.GEMINI_EMBEDDING_MODEL} (dim {config.EMBEDDING_DIM})\n")
    chunk_vecs = gemini.embed([embedding_text(c["title"], c["content"]) for c in chunks], "RETRIEVAL_DOCUMENT")
    questions = ON_TOPIC + OFF_TOPIC
    q_vecs = gemini.embed(questions, "RETRIEVAL_QUERY")

    def best(qv):
        scored = sorted(((cosine(qv, cv), c["id"]) for cv, c in zip(chunk_vecs, chunks)), reverse=True)
        return scored[0], scored[1]

    results = {}
    for q, qv in zip(questions, q_vecs):
        (top, top_id), (second, second_id) = best(qv)
        results[q] = (top, top_id, second, second_id)

    for label, group in (("ON-TOPIC", ON_TOPIC), ("OFF-TOPIC", OFF_TOPIC)):
        print(f"{label}  (top cosine -> chunk | 2nd cosine -> chunk)")
        for q in sorted(group, key=lambda q: results[q][0], reverse=True):
            top, top_id, second, second_id = results[q]
            print(f"  {top:.3f} {top_id:<20} | {second:.3f} {second_id:<20} {q}")
        print()

    on = [results[q][0] for q in ON_TOPIC]
    off = [results[q][0] for q in OFF_TOPIC]
    print(f"on-topic  min {min(on):.3f}  median {statistics.median(on):.3f}  max {max(on):.3f}")
    print(f"off-topic min {min(off):.3f}  median {statistics.median(off):.3f}  max {max(off):.3f}")
    if max(off) >= min(on):
        print("\nWARNING: ranges overlap - no floor separates them cleanly. Questions in the overlap:")
        for q in questions:
            if min(on) <= results[q][0] <= max(off):
                print(f"  {results[q][0]:.3f}  {'ON ' if q in ON_TOPIC else 'OFF'}  {q}")
    floor = (max(off) + min(on)) / 2
    ceiling = statistics.quantiles(on, n=10)[-1]
    print(f"\nSuggested SIMILARITY_FLOOR   = {floor:.2f}")
    print(f"Suggested SIMILARITY_CEILING = {ceiling:.2f}")
    print(f"(current config: floor {config.SIMILARITY_FLOOR}, ceiling {config.SIMILARITY_CEILING})")


if __name__ == "__main__":
    main()
