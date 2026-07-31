"""
Pluggable strategies for inferring a unit's mastery Bloom level from
per-question results.

Swapping the inference algorithm later (e.g. a model-based approach) only
requires providing a new MasteryInferenceStrategy to MasteryService - the
persistence layer, API contract, and dashboard stay untouched.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional

BLOOM_LEVELS = ["C1", "C2", "C3", "C4", "C5", "C6"]


def bloom_level_rank(level: Optional[str]) -> int:
    """Ordinal rank of a Bloom level (C1=1 ... C6=6); 0 if unset/unrecognized."""
    if not level:
        return 0
    try:
        return BLOOM_LEVELS.index(level.upper()) + 1
    except ValueError:
        return 0


class MasteryInferenceStrategy(ABC):
    """Interface for inferring a unit's mastery level from its per-Bloom-level correctness."""

    method_name: str = "unknown"

    @abstractmethod
    def infer_unit_mastery_level(self, bloom_correctness: Dict[str, bool]) -> Optional[str]:
        """
        Args:
            bloom_correctness: mapping of Bloom level (C1-C6) answered in the unit
                to whether that question was answered correctly.

        Returns:
            The inferred Bloom mastery level (e.g. "C4"), or None if no level
            was answered correctly.
        """
        raise NotImplementedError


class ManualMasteryInference(MasteryInferenceStrategy):
    """
    Baseline rule-based inference: a unit's mastery level is the highest
    Bloom level the learner answered correctly within that unit.
    """

    method_name = "manual"

    def infer_unit_mastery_level(self, bloom_correctness: Dict[str, bool]) -> Optional[str]:
        correct_levels = [level for level, correct in bloom_correctness.items() if correct]
        if not correct_levels:
            return None
        return max(correct_levels, key=bloom_level_rank)
