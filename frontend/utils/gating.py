"""
Test/Practice availability gating.

Driven entirely by the existing mastery summary
(GET /api/quiz/mastery-summary, via utils/quiz_api.py::get_mastery_summary)
- no new backend state needed. Single source of truth used by both the
sidebar (to disable nav buttons) and each page itself (as a guard, in case
a page is reached some other way).

Rule: a Test (the Placement Test) is taken exactly ONCE, ever - there is no
retake, regardless of Pass/Fail or later mastery changes:
- No completed Test yet -> Test enabled (it's the one-time Placement
  Test), Practice disabled.
- A Test has been completed -> Test permanently disabled, Practice
  permanently enabled - Practice is the sole ongoing mechanism for
  reaching/improving mastery from then on (see
  MasteryService.get_effective_remedial_units for how Practice results
  keep refining what's still recommended).

The backend enforces the one-time rule too (QuizService.start_quiz
refuses a second attempt) - this frontend gate is what disables the
Start button/shows the explanatory message before that server call ever
happens.
"""

from utils.quiz_api import get_mastery_summary


def get_learning_gating() -> dict:
    """
    Returns:
        Dictionary with:
        - test_enabled (bool): True only before the one-time Test has
          been completed.
        - practice_enabled (bool): True for the rest of the user's
          lifetime once the Test is done - Practice never gets disabled
          again, even once every unit is Mastered (there's simply nothing
          left to recommend at that point, which Practice's own start
          screen communicates).
        - has_attempts (bool), current_status ("PASS"/"FAIL")
        - is_placement_test (bool): True before the one-time Test - kept
          as its own field (rather than folding into test_enabled) since
          it's also used for "Placement Test" vs generic labeling.
    """
    summary = get_mastery_summary()
    has_attempts = bool(summary.get("has_attempts"))
    current_status = summary.get("current_status", "FAIL")

    test_enabled = not has_attempts
    practice_enabled = has_attempts

    return {
        "test_enabled": test_enabled,
        "practice_enabled": practice_enabled,
        "has_attempts": has_attempts,
        "current_status": current_status,
        "is_placement_test": not has_attempts,
    }
