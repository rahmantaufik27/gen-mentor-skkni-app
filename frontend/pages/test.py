"""
Test Page Component for Streamlit (formerly "Quiz")

Route Protection:
- Requires authentication (redirects to login if not authenticated)
- Only accessible to authenticated users
- Displays personalized test assessment for learners

The underlying scoring/mastery logic (utils/quiz_api.py, still calling the
existing /api/quiz/* endpoints) is unchanged - only presentation/naming and
availability gating are new here. See utils/gating.py for the Test/Practice
eligibility rule: the first Test is the Placement Test; after that, Test
stays eligible only while all six units are Mastered, otherwise Test is
ineligible and Practice is eligible instead. The page/menu are never hidden
or disabled - only the Start button on render_test_start() is, alongside an
inline message explaining why.
"""

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


def render_test_start():
    """
    Render test start screen. Always visible - eligibility (see
    utils/gating.py) only disables the Start button below, with an inline
    message explaining why; the page and sidebar menu are never hidden.
    """
    gating = get_learning_gating()
    is_placement = gating["is_placement_test"]
    heading = "Start Your Placement Test" if is_placement else "Start a New Test"

    with st.container(border=True):
        st.markdown(f"#### 📝 {heading}")

    if not gating["test_enabled"]:
        st.warning(
            "⚠️ Test is currently unavailable. Some of your units still need work - "
            "head to Practice to reinforce them, then come back to try Test again."
        )

    col1, col2 = st.columns(2)

    with col1:
        if is_placement:
            st.markdown("""
            #### Test Information
            - **Total Questions:** 36
            - **Question Types:** Multiple Choice
            - **Time Limit:** No time limit
            - **Randomization:** Questions are randomized for each attempt
            - This placement test assesses your current knowledge across all six units.

            #### How to Take the Test
            1. Click "Start Test" to begin
            2. Answer each question by selecting one option
            3. Click "Next Question" to proceed
            4. Review your progress at the top
            5. Complete all questions to see results
            """)
        else:
            st.markdown("""
            #### Test Information
            - **Total Questions:** 36
            - **Question Types:** Multiple Choice
            - **Time Limit:** No time limit
            - **Randomization:** Questions are randomized for each attempt

            #### How to Take the Test
            1. Click "Start Test" to begin
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
        """)

    st.divider()

    button_label = "🚀 Start Placement Test" if is_placement else "🚀 Start Test"
    if st.button(
        button_label, use_container_width=True, type="primary",
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

        col1, col2, col3 = st.columns(3)

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

        # View progress
        with col2:
            if st.button("View Progress", use_container_width=True):
                st.info(f"Answered: {question_number} / {total_questions}")

        # Quit test
        with col3:
            if st.button("Exit Test", use_container_width=True):
                st.session_state.test_started = False
                st.session_state.test_current_question = 0
                st.session_state.test_session_id = None
                st.rerun()


def render_test_results():
    """Render test results with mastery information"""
    result_data = st.session_state.test_result or {}

    # Display results header
    st.subheader("Test Complete!")
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

    # Action buttons - re-check gating now that this attempt just completed
    gating = get_learning_gating()
    # col1, col2, col3 = st.columns(3)
    col1, col2 = st.columns(2)

    with col1:
        if gating["test_enabled"]:
            if st.button("Take Another Test", use_container_width=True, type="primary"):
                st.session_state.test_started = False
                st.session_state.test_current_question = 0
                st.session_state.test_session_id = None
                st.session_state.test_completed = False
                st.session_state.test_result = None
                st.rerun()
        else:
            if st.button("Go to Practice", use_container_width=True, type="primary"):
                st.session_state.test_started = False
                st.session_state.test_current_question = 0
                st.session_state.test_session_id = None
                st.session_state.test_completed = False
                st.session_state.test_result = None
                st.session_state.current_page = "practice"
                st.rerun()

    # with col2:
    #     if st.button("View Test History", use_container_width=True):
    #         show_test_history()

    with col2:
        if st.button("Go Home", use_container_width=True):
            st.session_state.test_started = False
            st.session_state.test_current_question = 0
            st.session_state.test_session_id = None
            st.session_state.test_completed = False
            st.session_state.test_result = None
            st.session_state.current_page = "profile"
            st.rerun()


def show_test_history():
    """Show user's test history"""
    history_result = get_quiz_history(limit=10)

    if history_result.get("success"):
        attempts = history_result.get("attempts", [])

        st.subheader("Your Test History")

        if attempts:
            for idx, attempt in enumerate(attempts, 1):
                with st.expander(f"Attempt {idx} - {attempt.get('status')}"):
                    col1, col2, col3 = st.columns(3)

                    with col1:
                        st.write(f"**Score:** {attempt.get('total_score')} points")

                    with col2:
                        st.write(f"**Correct:** {attempt.get('correct_answers')}/{attempt.get('total_questions')}")

                    with col3:
                        status = attempt.get('status', 'UNKNOWN')
                        st.write(f"**Status:** {status}")

                    st.write(f"**Date:** {attempt.get('completed_at')}")
        else:
            st.info("No test attempts yet")
    else:
        st.error(f"Failed to load history: {history_result.get('error')}")


def show_all_test_results():
    """Show all results summary"""
    history_result = get_quiz_history(limit=100)

    if history_result.get("success"):
        attempts = history_result.get("attempts", [])

        st.subheader("All Test Results")

        if attempts:
            # Summary stats
            total_attempts = len(attempts)
            passed = sum(1 for a in attempts if a.get('status') == 'PASS')
            failed = total_attempts - passed
            avg_score = sum(a.get('total_score', 0) for a in attempts) / total_attempts if total_attempts > 0 else 0

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Total Attempts", total_attempts)

            with col2:
                st.metric("Passed", passed)

            with col3:
                st.metric("Failed", failed)

            with col4:
                st.metric("Avg Score", f"{avg_score:.1f}")

            st.divider()

            # Show recent attempts
            st.subheader("Recent Attempts")
            show_test_history()
        else:
            st.info("No test attempts yet")
    else:
        st.error(f"Failed to load results: {history_result.get('error')}")


# ============================================================================
# EXECUTE TEST PAGE
# ============================================================================
# Call render_test_page directly (this executes when page is imported/exec'd)
render_test_page()
