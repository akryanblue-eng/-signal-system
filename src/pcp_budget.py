"""
Budget grading functor for the proof-carrying projection kernel.

Budget is a STRUCTURAL INVARIANT of morphisms, derived from term shape.
It is not a runtime parameter — it cannot be passed in or changed after certification.

Composition law (max, not min):
    deg(π₂ ∘ π₁) = max(deg(π₁), deg(π₂))

Composition inherits the worst constraint; authority cannot be diluted.
RestrictBudget can only LOWER a declared grade — never amplify.
"""
from enum import IntEnum


class BudgetGrade(IntEnum):
    STREAMING_NO_LOOKAHEAD = 0
    BATCH_LOOKAHEAD_K = 1
    NO_ALLOCATION = 2
    INDEXED_ALLOWED = 3


def compose_grade(g1: BudgetGrade, g2: BudgetGrade) -> BudgetGrade:
    """Grade of composed morphism = max of component grades."""
    return BudgetGrade(max(g1, g2))
