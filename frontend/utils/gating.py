"""
Test/Practice availability gating.

Driven entirely by the existing mastery summary
(GET /api/quiz/mastery-summary, via utils/quiz_api.py::get_mastery_summary)
- no new backend state needed. Single source of truth used by both the
sidebar (to disable nav buttons) and each page itself (as a guard, in case
a page is reached some other way).

Rule: the Test is a TWO-stage progression, each stage taken exactly ONCE:
- No Pre-Test yet -> Pre-Test enabled (the one-time Placement Test),
  Practice disabled.
- Pre-Test done -> Practice enabled. The Test stays disabled UNTIL the
  learner clears every Practice recommendation (all units reach their
  target Knowledge Level - i.e. no effective_remedial_units left), at
  which point the Post-Test unlocks.
- Post-Test done -> Test permanently disabled; Practice stays enabled as
  the ongoing mechanism.

The next stage and its availability are computed server-side in the mastery
summary (next_test_stage / post_test_available - see
MasteryService.get_user_mastery_summary), and QuizService.start_quiz
enforces the same rule; this frontend gate just mirrors it to disable the
Start button / show the right explanatory message before any server call.
"""

from turtle import st

from utils.quiz_api import get_mastery_summary
from utils.practice_api import get_practice_analytics, complete_practice

def get_learning_gating() -> dict:
    """
    Returns:
        Dictionary with:
        - test_enabled (bool): True when a Test stage is startable now -
          before the Pre-Test, or once the Post-Test has unlocked.
        - practice_enabled (bool): True for the rest of the user's
          lifetime once the Pre-Test is done - Practice never gets
          disabled again.
        - has_attempts (bool), current_status ("PASS"/"FAIL")
        - is_placement_test (bool): True before the Pre-Test - also used
          for "Placement Test" vs generic labeling.
        - test_stage ("pre"/"post"/None): the stage that would start now,
          or None if no Test is currently available.
        - pre_test_completed / post_test_completed / post_test_available
          (bool): the raw progression flags, for stage-aware messaging.
    """
    summary = get_mastery_summary()
    has_attempts = bool(summary.get("has_attempts"))
    current_status = summary.get("current_status", "FAIL")

    # Progression flags from the backend. Fall back to the legacy one-time
    # behavior (Pre-Test only) if an older backend doesn't send them yet.
    pre_test_completed = bool(summary.get("pre_test_completed", has_attempts))
    post_test_completed = bool(summary.get("post_test_completed", False))
    post_test_available = bool(summary.get("post_test_available", False))
    next_test_stage = summary.get(
        "next_test_stage",
        "pre" if not pre_test_completed else None,
    )

    test_enabled = next_test_stage is not None
    practice_enabled = has_attempts

    return {
        "test_enabled": test_enabled,
        "practice_enabled": practice_enabled,
        "has_attempts": has_attempts,
        "current_status": current_status,
        "is_placement_test": not pre_test_completed,
        "test_stage": next_test_stage,
        "pre_test_completed": pre_test_completed,
        "post_test_completed": post_test_completed,
        "post_test_available": post_test_available,
    }

def get_content_unlock_state() -> dict:
    """
    Whether Learning Path content (Materials, Chatbot, Notes, Reflection...)
    is unlocked yet: true once the learner has completed at least one Test
    stage (Pre/Post) or one Practice session.
    """
    unlocked = bool(st.session_state.get("content_unlocked_this_session"))
    return {"unlocked": unlocked}

    # gating = get_learning_gating()  # already fetches mastery summary
    # practice = get_practice_analytics()
    # # complete_practice(st.session_state.get("practice_session_id", ""))  # ensure any in-progress session is finalized 
    # has_completed = bool(practice.get("success") and practice.get("total_sessions", 0) > 0)

    # # has_practice = bool(practice.get("success") and practice.get("total_sessions", 0) > 0)
    # # unlocked = gating["has_attempts"] or has_practice
    # unlocked = gating["has_attempts"] or has_completed

    # # return {"unlocked": unlocked, "has_attempts": gating["has_attempts"], "has_practice": has_practice}
    # return {"unlocked": unlocked, "has_attempts": gating["has_attempts"], "has_completed": has_completed}
