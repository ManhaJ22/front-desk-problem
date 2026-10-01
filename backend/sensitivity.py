"""Sensitivity classification (one structured LLM call) and the is_sensitive rule.

Sensitive = category != none OR normalized score >= SENSITIVITY_THRESHOLD (decision log #18).
Sensitive questions always escalate.
"""

from backend import config, gemini
from backend.schemas import SensitivityCategory, SensitivityResult

SYSTEM_INSTRUCTION = """\
You classify questions that parents send to the front desk of a daycare / pre-K.
You do NOT answer the question. You decide how sensitive it is.

Pick exactly one category:
- health: illness, symptoms, fever, injuries, medication, a child's physical wellbeing.
  Example: "My son threw up last night, can he come in?"
- safety: physical safety, emergencies, incidents, who is allowed to pick a child up.
  Example: "Someone who isn't on my list says they're picking up my daughter."
- allergies: food or other allergies, reactions, EpiPens, medically required diets.
  Example: "My kid is allergic to sesame, is the snack safe?"
- custody_legal: custody arrangements, court or restraining orders, disputes between guardians.
  Example: "My ex isn't allowed to pick up our son, what do I need to give you?"
- emotional_social: a child's emotional wellbeing, behavior, biting, bullying, family stress.
  Example: "My daughter cries every morning at drop-off, is that normal?"
- none: routine logistics such as hours, holidays, tuition, tours, meals, supplies.
  Example: "Are you open on Veterans Day?"

Score from 1 to 5 how much the question needs a human to handle it:
1 = routine, an automated answer is fine; 3 = some care needed; 5 = staff must handle it.

Rationale: one short sentence explaining the category and score.
"""


def classify(question: str) -> SensitivityResult:
    """The model sees the question only, never handbook text."""
    result = gemini.generate_structured(f"Parent's question:\n{question}", SYSTEM_INSTRUCTION, SensitivityResult)
    result.score = max(1, min(5, result.score))
    return result


def normalized(score: int) -> float:
    """1 -> 0.0, 2 -> 0.25, 3 -> 0.5, 4 -> 0.75, 5 -> 1.0"""
    return (score - 1) / 4


def is_sensitive(result: SensitivityResult) -> bool:
    return result.category != SensitivityCategory.none or normalized(result.score) >= config.SENSITIVITY_THRESHOLD
