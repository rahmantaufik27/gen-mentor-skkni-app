"""
Test/Practice availability gating.

Driven entirely by the existing mastery summary
(GET /api/quiz/mastery-summary, via utils/quiz_api.py::get_mastery_summary)
- no new backend state needed. Single source of truth used by both the
sidebar (to disable nav buttons) and each page itself (as a guard, in case
a page is reached some other way).

Rule:
- No completed Test yet -> the next Test is the Placement Test: Test
  enabled, Practice disabled.
- Latest Test resulted in all six units Mastered -> Test enabled (there's
  nothing left to practice), Practice disabled.
- Otherwise (completed at least one Test, not all units Mastered yet) ->
  Test disabled, Practice enabled.
"""

from utils.quiz_api import get_mastery_summary


def get_learning_gating() -> dict:
    """
    Returns:
        Dictionary with:
        - test_enabled (bool), practice_enabled (bool)
        - has_attempts (bool), current_status ("PASS"/"FAIL")
        - is_placement_test (bool): True when the next Test to take is the
          user's first (the Placement Test)
    """
    summary = get_mastery_summary()
    has_attempts = bool(summary.get("has_attempts"))
    current_status = summary.get("current_status", "FAIL")

    if not has_attempts or current_status == "PASS":
        test_enabled, practice_enabled = True, False
    else:
        test_enabled, practice_enabled = False, True

    return {
        "test_enabled": test_enabled,
        "practice_enabled": practice_enabled,
        "has_attempts": has_attempts,
        "current_status": current_status,
        "is_placement_test": not has_attempts,
    }
