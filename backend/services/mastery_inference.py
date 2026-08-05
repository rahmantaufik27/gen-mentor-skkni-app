"""
Pluggable strategies for inferring a unit's mastery Bloom level from
per-question results.

Swapping the inference algorithm later (e.g. a model-based approach) only
requires providing a new MasteryInferenceStrategy to MasteryService - the
persistence layer, API contract, and dashboard stay untouched. Two
strategies exist today:
- ManualMasteryInference: rule-based (highest correctly-answered Bloom level).
- DBNMasteryInference: one Dynamic Bayesian Network per unit, inferring the
  Knowledge Level via the Forward Algorithm - see its class docstring below.

Both Test (MasteryService.compute_and_save_unit_mastery) and Practice
(PracticeService._save_practice_attempt) resolve the SAME strategy for a
user (see MasteryService.resolve_strategy) and call
new_instance_for_unit(unit_code) before inferring each unit - so a unit's
observations, probabilities, and hidden state never mix with another
unit's, regardless of which flow is calling in.
"""

import json
import logging
import os
from abc import ABC, abstractmethod
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional, Tuple

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
    """Interface for inferring a unit's mastery level from its per-question results."""

    # Identifies which strategy produced a result (not persisted - the
    # user_mastery_level/practice_attempt_units tables have no method
    # column; which strategy ran is always re-derived from
    # users.inference_method, see MasteryService.resolve_strategy).
    method_name: str = "unknown"

    def new_instance_for_unit(self, unit_code: str) -> "MasteryInferenceStrategy":
        """
        Return the strategy instance to use for one specific unit's
        inference. Stateless strategies (e.g. Manual) can safely return
        themselves; strategies that need per-unit isolation for logging/
        debugging (e.g. DBN - "one DBN per unit") must return a fresh
        instance here, scoped to that unit only.
        """
        return self

    def infer_unit_mastery_level(self, bloom_correctness: Dict[str, bool]) -> Optional[str]:
        """
        Convenience form for data with at most one question per Bloom
        level (Test: quiz_attempt_details has exactly one C1-C6 question
        per unit). Internally converts to the ordered observation sequence
        and delegates to infer_from_observations.

        Args:
            bloom_correctness: mapping of Bloom level (C1-C6) answered in the unit
                to whether that question was answered correctly.

        Returns:
            The inferred Bloom mastery level (e.g. "C4"), or None if no
            question was observed for this unit.
        """
        observations = [
            (level, bloom_correctness[level]) for level in BLOOM_LEVELS if level in bloom_correctness
        ]
        return self.infer_from_observations(observations)

    @abstractmethod
    def infer_from_observations(self, observations: List[Tuple[str, bool]]) -> Optional[str]:
        """
        Core entry point: the unit's Question Response observations in
        quiz order, as (question_level, is_correct) pairs. May contain
        repeats (e.g. Practice, which can serve multiple questions at the
        same Bloom level for a unit in one session) - unlike
        infer_unit_mastery_level's dict form, nothing here is deduplicated.

        Returns:
            The inferred Bloom mastery level (e.g. "C4"), or None if
            `observations` is empty.
        """
        raise NotImplementedError


class ManualMasteryInference(MasteryInferenceStrategy):
    """
    Baseline rule-based inference: a unit's mastery level is the highest
    Bloom level the learner answered correctly within that unit.
    """

    method_name = "manual"

    def infer_from_observations(self, observations: List[Tuple[str, bool]]) -> Optional[str]:
        correct_levels = [level for level, is_correct in observations if is_correct]
        if not correct_levels:
            return None
        return max(correct_levels, key=bloom_level_rank)


_dbn_config_cache: Optional[Dict] = None


def _load_dbn_config() -> Dict:
    """
    Load DBN parameters (prior/transition/emission) from data/dbn_config.json,
    cached process-wide after the first read (same singleton-cache pattern as
    services/neo4j_service.py::get_neo4j_service()). A change to the config
    file requires a process restart to take effect, same as knowledge_target.json.
    """
    global _dbn_config_cache
    if _dbn_config_cache is None:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(backend_dir, "data", "dbn_config.json")
        with open(path, "r", encoding="utf-8") as f:
            _dbn_config_cache = json.load(f)
    return _dbn_config_cache


def _build_dbn_logger() -> logging.Logger:
    """Dedicated logger writing to backend/logs/dbn.log (rotated at 2MB, 3 backups) - same pattern as services/neo4j_service.py::_build_logger()."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(backend_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("dbn_inference")
    logger.setLevel(logging.INFO)
    if not logger.handlers:  # avoid duplicate handlers if the module is reloaded
        handler = RotatingFileHandler(
            os.path.join(log_dir, "dbn.log"), maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    return logger


_dbn_logger = _build_dbn_logger()


def _fmt_posterior(alpha: Dict[str, float]) -> str:
    """Compact, readable posterior for log lines, e.g. 'C1=0.12 C2=0.34 ...'."""
    return " ".join(f"{state}={alpha[state]:.4f}" for state in BLOOM_LEVELS if state in alpha)


class DBNMasteryInference(MasteryInferenceStrategy):
    """
    One Dynamic Bayesian Network PER UNIT - new_instance_for_unit() always
    returns a fresh DBNMasteryInference scoped to a single unit_code, so
    two units' observations/posteriors/hidden states can never mix even
    when the same underlying strategy object is reused across a whole Test
    attempt or Practice session (see MasteryService.compute_and_save_unit_mastery
    / PracticeService._save_practice_attempt, both of which call
    new_instance_for_unit(unit_code) before inferring each unit).

    - Hidden state: Knowledge Level (C1-C6).
    - Dynamic state chain: Knowledge Level(t0) -> Knowledge Level(t1) -> ...
      -> Knowledge Level(tn), one step per question answered in the unit,
      processed strictly in quiz order (the order infer_from_observations
      receives them - see its callers for how that order is derived).
    - Observation: each hidden state emits a Question Response
      (Correct/Wrong), conditioned on the asked question's own Bloom/
      Knowledge Level (QC1-QC6).

    Parameters (prior/transition/emission) come from data/dbn_config.json
    (see _load_dbn_config), loaded once and shared read-only across every
    per-unit instance - only unit_code (used purely for log tracing) is
    unique per instance. Inference runs the Forward Algorithm over the
    observation sequence, updating the posterior after every single
    observation (see _forward_algorithm); the inferred Knowledge Level is
    the state with the highest posterior probability after the last one.
    Every step is logged to backend/logs/dbn.log for debugging.
    """

    method_name = "dbn"

    def __init__(self, config: Optional[Dict] = None, unit_code: Optional[str] = None):
        self.config = config or _load_dbn_config()
        self.unit_code = unit_code

    def new_instance_for_unit(self, unit_code: str) -> "DBNMasteryInference":
        # Shares self.config (read-only, loaded once) but is otherwise a
        # brand new instance - no state from any other unit's inference
        # carries over.
        return DBNMasteryInference(config=self.config, unit_code=unit_code)

    def infer_from_observations(self, observations: List[Tuple[str, bool]]) -> Optional[str]:
        unit_label = self.unit_code or "(unassigned unit)"
        if not observations:
            _dbn_logger.info("[unit=%s] no observations - skipping DBN inference", unit_label)
            return None

        _dbn_logger.info(
            "[unit=%s] starting DBN inference | prior=%s | observations=%s",
            unit_label, _fmt_posterior(self.config["prior"]), observations,
        )
        result = self._forward_algorithm(observations)
        _dbn_logger.info("[unit=%s] inferred Knowledge Level = %s", unit_label, result)
        return result

    def _forward_algorithm(self, observations: List[Tuple[str, bool]]) -> str:
        """
        Scaled Forward Algorithm: alpha_0(i) = prior(i) * emission(i, obs_0);
        alpha_t(i) = [sum_j alpha_{t-1}(j) * transition(j, i)] * emission(i, obs_t).
        Normalizing alpha after every step only rescales it (same argmax) and
        keeps the running product numerically stable over long sequences.
        The posterior (alpha) is recomputed after EVERY observation, in order.
        """
        unit_label = self.unit_code or "(unassigned unit)"
        prior = self.config["prior"]
        transition = self.config["transition"]

        question_level, is_correct = observations[0]
        alpha = {
            state: prior.get(state, 0.0) * self._emission_prob(state, question_level, is_correct)
            for state in BLOOM_LEVELS
        }
        alpha = self._normalize(alpha)
        _dbn_logger.info(
            "[unit=%s] t0 obs=(level=%s, %s) -> posterior: %s",
            unit_label, question_level, "correct" if is_correct else "wrong", _fmt_posterior(alpha),
        )

        for t, (question_level, is_correct) in enumerate(observations[1:], start=1):
            alpha = self._normalize({
                curr_state: sum(
                    alpha[prev_state] * transition.get(prev_state, {}).get(curr_state, 0.0)
                    for prev_state in BLOOM_LEVELS
                ) * self._emission_prob(curr_state, question_level, is_correct)
                for curr_state in BLOOM_LEVELS
            })
            _dbn_logger.info(
                "[unit=%s] t%d obs=(level=%s, %s) -> posterior: %s",
                unit_label, t, question_level, "correct" if is_correct else "wrong", _fmt_posterior(alpha),
            )

        return max(alpha, key=alpha.get)

    def _emission_prob(self, hidden_state: str, question_level: str, is_correct: bool) -> float:
        """P(Question Response = correct/wrong | Knowledge Level = hidden_state, Question Level = question_level)."""
        outcome_key = "correct" if is_correct else "wrong"
        question_key = f"Q{question_level}"  # e.g. "C3" -> "QC3", matching dbn_config.json's emission keys
        return self.config["emission"].get(outcome_key, {}).get(hidden_state, {}).get(question_key, 0.0)

    @staticmethod
    def _normalize(alpha: Dict[str, float]) -> Dict[str, float]:
        total = sum(alpha.values())
        if total <= 0:
            # Degenerate (misconfigured/zeroed) probabilities - fall back to
            # uniform rather than dividing by zero.
            return {state: 1.0 / len(alpha) for state in alpha}
        return {state: value / total for state, value in alpha.items()}
