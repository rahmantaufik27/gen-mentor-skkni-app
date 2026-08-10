"""
Test Page Component for Streamlit (formerly "Quiz")

Route Protection:
- Requires authentication (redirects to login if not authenticated)
- Only accessible to authenticated users
- Displays personalized test assessment for learners

The underlying scoring/mastery logic (utils/quiz_api.py, still calling the
existing /api/quiz/* endpoints) is unchanged - only presentation/naming and
availability gating are new here.

The Test (the Placement Test) is taken exactly ONCE, ever - see
utils/gating.py: test_enabled is True only before that one attempt, and
permanently False afterward (enforced server-side too, see
QuizService.start_quiz). There is no "retake"; Practice is the sole
ongoing mechanism from then on. The page/menu are never hidden or
disabled - only the Start button on render_test_start() is, alongside an
inline message explaining why.

Test History (show_test_history()) therefore shows at most ONE completed
result, not a multi-attempt list - contrast with Practice History
(components/mastery_dashboard.py), which tracks every repeatable Practice
session.
"""

import pandas as pd
import streamlit as st
from utils.quiz_api import (
    start_quiz, get_question, submit_answer,
    complete_quiz, get_quiz_history, get_unit_code_map
)
from utils.gating import get_learning_gating
from datetime import datetime
import json
# from utils.auth_guard import require_authentication


def _get_code_map() -> dict:
    """Truncated -> full unit_code map (see utils/quiz_api.py::get_unit_code_map and
    components/mastery_dashboard.py's identical helper). Falls back to an empty map on
    failure so callers can always .get(code, code) without special-casing errors."""
    result = get_unit_code_map()
    return result.get("unit_codes", {}) if result.get("success") else {}


def initialize_test_state():
    """Initialize test session state"""
    if "test_session_id" not in st.session_state:
        st.session_state.test_session_id = None
    if "test_current_question" not in st.session_state:
        st.session_state.test_current_question = 0
    if "test_started" not in st.session_state:
        st.session_state.test_started = False
    if "test_completed" not in st.session_state:
        st.session_state.test_completed = False
    if "test_result" not in st.session_state:
        st.session_state.test_result = None


def render_test_page():
    """Render the main test page"""
    # NOTE: st.set_page_config() is called by main.py, not here

    initialize_test_state()

    # Test not started
    if not st.session_state.test_started:
        render_test_start()

    # Test in progress
    elif st.session_state.test_started and not st.session_state.test_completed:
        render_test_progress()

    # Test completed
    else:
        render_test_results()


def _stage_label(stage: str) -> str:
    """Human label for a test stage."""
    return "Post-Test" if stage == "post" else "Pre-Test"


def render_test_start():
    """
    Render test start screen. Always visible - eligibility (see
    utils/gating.py) only disables the Start button below, with an inline
    message explaining why; the page and sidebar menu are never hidden.

    The Test is a two-stage progression (Pre-Test then Post-Test). The
    screen adapts its framing to whichever stage is next:
    - Pre-Test available  -> Placement/Pre-Test framing, Start enabled.
    - Pre-Test done, Post-Test not yet unlocked -> Start disabled, with a
      message pointing the learner to finish their Practice recommendations.
    - Post-Test unlocked   -> Post-Test framing, Start enabled.
    - Both stages done     -> Start disabled, Practice presented as ongoing.
    """
    gating = get_learning_gating()
    # What this screen is *about*: the Pre-Test until it's done, then the
    # Post-Test from that point on (whether it's available now, still locked
    # behind Practice, or already completed).
    display_stage = "post" if gating.get("pre_test_completed") else "pre"
    stage_name = _stage_label(display_stage)

    with st.container(border=True):
        st.markdown(f"#### 📝 Start Your {stage_name}")

    if not gating["test_enabled"]:
        if gating.get("post_test_completed"):
            st.warning(
                "⚠️ You've completed both your Pre-Test and Post-Test. "
                "Head to Practice to keep improving your units."
            )
        else:
            # Pre-Test done, Post-Test still locked: Practice recommendations remain.
            st.warning(
                "⚠️ Your **Post-Test** isn't available yet. Clear your remaining "
                "Practice recommendations - get every unit to its target Knowledge "
                "Level - and the Post-Test will unlock here."
            )

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        #### {stage_name} Information
        - **Total Questions:** 36
        - **Question Types:** Multiple Choice
        - **Time Limit:** No time limit
        - **Randomization:** Questions are randomized
        - The {stage_name} assesses your knowledge across all six units.
        - The Test has two stages: the **Pre-Test** first, then the
          **Post-Test** once you've cleared every Practice recommendation.

        #### How to Take the Test
        1. Click "Start {stage_name}" to begin
        2. Answer each question by selecting one option
        3. Click "Next Question" to proceed
        4. Review your progress at the top
        5. Complete all questions to see results
        """)

    with col2:
        st.info("""
        ✅ **Tips for Success**
        - Read each question carefully
        - Consider all options before answering
        - You cannot go back to previous questions
        - Results will show your score, pass/fail status, and detailed review
        - Between the Pre-Test and Post-Test, Practice lets you keep
          reinforcing your weakest units as many times as you like
        """)

    st.divider()

    if st.button(
        f"Start {stage_name}", use_container_width=True, type="primary",
        key="start_test_btn", disabled=not gating["test_enabled"],
    ):
        result = start_quiz()

        if result.get("success"):
            st.session_state.test_session_id = result.get("session_id")
            st.session_state.test_current_question = 0
            st.session_state.test_started = True
            st.session_state.test_completed = False
            st.rerun()
        else:
            st.error(f"Failed to start test: {result.get('error', 'Unknown error')}")

    if not gating["test_enabled"]:
        if st.button("Go to Practice", use_container_width=True, key="test_disabled_go_practice"):
            st.session_state.current_page = "practice"
            st.rerun()


def render_test_progress():
    """Render test in progress"""
    session_id = st.session_state.test_session_id
    question_index = st.session_state.test_current_question

    # Get current question
    question_result = get_question(session_id, question_index)
    if not question_result.get("success"):
        st.error("Failed to load question")
        return

    # Question data is at root level of response (not nested under "question" key)
    total_questions = question_result.get("total_questions", 36)
    question_number = question_result.get("question_number", question_index + 1)
    question_text = question_result.get("question_text", "")
    unit = question_result.get("unit", "")
    bloom_level = question_result.get("bloom_level", "")
    choices = question_result.get("choices", [])

    # Progress bar
    progress_percentage = question_number / total_questions
    st.progress(progress_percentage, text=f"Progress: {question_number}/{total_questions} questions")

    st.divider()

    # Display question
    st.subheader(f"Question {question_number} of {total_questions}")

    # Unit and Bloom info
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Unit:** {unit}")
    with col2:
        st.write(f"**Bloom Level:** {bloom_level}")

    st.divider()

    st.write(f"### {question_text}")

    # Answer options
    if not choices:
        st.warning("No answer choices available")
        return

    # Create choice text with letters
    choice_options = [f"{choice.get('id')}. {choice.get('text')}" for choice in choices]

    # Store selected answer
    selected_text = st.radio(
        label="Select your answer:",
        options=choice_options,
        key=f"test_question_{question_number}"
    )

    # Get choice ID from selection
    if selected_text:
        selected_choice_id = selected_text.split(".")[0]  # Extract letter (A, B, C, D)

        st.divider()

        col1, col2 = st.columns(2)

        # Submit answer
        with col1:
            if st.button("Submit Answer", use_container_width=True, type="primary"):
                submit_result = submit_answer(
                    session_id,
                    question_index,
                    selected_choice_id
                )

                if submit_result.get("success"):
                    progress_data = submit_result.get("progress", {})

                    # Check if test is completed
                    if progress_data.get("answered") >= total_questions:
                        # Test finished - auto-complete
                        complete_result = complete_quiz(session_id)
                        if complete_result.get("success"):
                            st.session_state.test_completed = True
                            st.session_state.test_result = complete_result
                            st.rerun()
                    else:
                        # Move to next question
                        st.session_state.test_current_question += 1
                        st.rerun()
                else:
                    st.error(f"Failed to submit answer: {submit_result.get('error')}")

        # Quit test
        with col2:
            if st.button("Exit Test", use_container_width=True):
                st.session_state.test_started = False
                st.session_state.test_current_question = 0
                st.session_state.test_session_id = None
                st.rerun()


def render_test_results():
    """Render test results with mastery information"""
    result_data = st.session_state.test_result or {}

    # Display results header (stage-aware: Pre-Test vs Post-Test)
    stage_name = _stage_label(result_data.get("test_stage", "pre"))
    st.subheader(f"{stage_name} Complete!")
    st.divider()

    # Main score display
    col1, col2, col3, col4 = st.columns(4)

    total_questions = result_data.get("total_questions", 0)
    correct_answers = result_data.get("correct_answers", 0)
    max_score = result_data.get("max_possible_score", 1)
    total_score = result_data.get("total_score", 0)

    with col1:
        score_percentage = (total_score / max_score * 100) if max_score > 0 else 0
        st.metric(
            "Score",
            f"{score_percentage:.1f}%",
            delta=f"{correct_answers}/{total_questions}"
        )

    with col2:
        status = "PASSED" if result_data.get("is_passed") else "FAILED"
        st.metric("Status", status)

    with col3:
        st.metric("Total Points", f"{total_score}")

    with col4:
        st.metric("Max Possible", f"{max_score}")

    st.divider()

    # Pass/Fail determination
    is_passed = result_data.get("is_passed", False)

    if is_passed:
        st.success(f"Congratulations! You passed the test!")
    else:
        st.warning(f"You did not pass this time. Keep practicing!")

    st.divider()

    # Unit Mastery Summary
    st.subheader("Unit Mastery Summary")

    unit_mastery = result_data.get("unit_mastery", {})
    mastered_units = result_data.get("mastered_units", [])
    remedial_units = result_data.get("remedial_units", [])
    code_map = _get_code_map()

    if unit_mastery:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("### Mastered Units")
            if mastered_units:
                for unit in mastered_units:
                    unit_data = unit_mastery.get(unit, {})
                    score = unit_data.get("score", 0)
                    max_s = unit_data.get("max", 21)
                    st.success(f"{code_map.get(unit, unit)}: {score}/{max_s} points")
            else:
                st.info("No units mastered yet")

        with col2:
            st.markdown("### Remedial Units (Need Improvement)")
            if remedial_units:
                for unit in remedial_units:
                    unit_data = unit_mastery.get(unit, {})
                    score = unit_data.get("score", 0)
                    max_s = unit_data.get("max", 21)
                    st.warning(f"{code_map.get(unit, unit)}: {score}/{max_s} points")
            else:
                st.info("All units mastered!")

    st.divider()

    # Action buttons. Test can never be retaken (see utils/gating.py /
    # QuizService.start_quiz), so there is no "Take Another Test" option
    # here - Practice is always the next step forward from this screen.
    if "test_show_review" not in st.session_state:
        st.session_state.test_show_review = False

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Go to Practice", use_container_width=True, type="primary"):
            st.session_state.test_started = False
            st.session_state.test_current_question = 0
            st.session_state.test_session_id = None
            st.session_state.test_completed = False
            st.session_state.test_result = None
            st.session_state.current_page = "practice"
            st.rerun()

    with col2:
        review_label = "Hide Test Review" if st.session_state.test_show_review else "View Test Review"
        if st.button(review_label, use_container_width=True):
            st.session_state.test_show_review = not st.session_state.test_show_review
            st.rerun()

    with col3:
        if st.button("Go Home", use_container_width=True):
            st.session_state.test_started = False
            st.session_state.test_current_question = 0
            st.session_state.test_session_id = None
            st.session_state.test_completed = False
            st.session_state.test_result = None
            st.session_state.current_page = "profile"
            st.rerun()

    if st.session_state.test_show_review:
        show_test_history()


def show_test_history():
    """
    Show the user's test history across BOTH stages (Pre-Test and Post-Test).
    Each attempt is shown under its stage label with a detailed Question
    Review table in the same format as Practice Review (see
    components/practice.py::_render_practice_review) - Question No. / Unit /
    Question Knowledge Level / User Answer / Result.
    """
    # At most two entries in practice (Pre-Test + Post-Test); limit=10 is a
    # defensive ceiling. Attempts come back newest-first.
    history_result = get_quiz_history(limit=10)

    if history_result.get("success"):
        attempts = history_result.get("attempts", [])
        code_map = _get_code_map()

        st.subheader("Your Test History")

        if not attempts:
            st.info("No test attempt yet")
            return

        for attempt in attempts:
            stage_name = _stage_label(attempt.get("test_stage", "pre"))
            st.markdown(f"##### {stage_name}")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.write(f"**Score:** {attempt.get('total_score')} points")

            with col2:
                st.write(f"**Correct:** {attempt.get('correct_answers')}/{attempt.get('total_questions')}")

            with col3:
                st.write(f"**Status:** {attempt.get('status', 'UNKNOWN')}")

            st.write(f"**Date:** {attempt.get('completed_at')}")

            review = attempt.get("review", [])
            if review:
                st.markdown("")
                st.markdown("###### Question Review")
                review_df = pd.DataFrame([
                    {
                        "Question No.": r["question_number"],
                        "Unit": code_map.get(r["unit_code"], r["unit_code"]),
                        "Question Knowledge Level": r["bloom_level"],
                        "User Answer": r["user_answer"],
                        "Result": "✅ Correct" if r["is_correct"] else "❌ Wrong",
                    }
                    for r in review
                ])
                st.dataframe(review_df, use_container_width=True, hide_index=True)

            st.divider()
    else:
        st.error(f"Failed to load history: {history_result.get('error')}")


# ============================================================================
# EXECUTE TEST PAGE
# ============================================================================
# Call render_test_page directly (this executes when page is imported/exec'd)
render_test_page()
