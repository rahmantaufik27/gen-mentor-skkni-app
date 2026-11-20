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
from utils.theme import render_exam_navigator, confirm_exam_action
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
    if "test_question_status" not in st.session_state:
        st.session_state.test_question_status = {}
    if "test_view_index" not in st.session_state:
        st.session_state.test_view_index = None
    if "test_question_answers" not in st.session_state:
        # 0-based question index -> previously selected choice letter, so
        # revisiting an answered question pre-selects what was chosen
        # before (and lets the learner change it - submit_answer upserts
        # by index server-side, so resubmitting never double-counts).
        st.session_state.test_question_answers = {}


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
    """Render test in progress.

    Same frontier/view-index/status pattern as Practice (see
    components/practice.py::_render_practice_progress for the full
    rationale) - duplicated here rather than shared, since Test's
    backend calls (submit_answer/complete_quiz from utils/quiz_api) are
    a different module than Practice's."""
    session_id = st.session_state.test_session_id
    frontier_index = st.session_state.test_current_question
    status = st.session_state.test_question_status

    view_index = st.session_state.test_view_index
    if view_index is None:
        view_index = frontier_index
    is_frontier = view_index == frontier_index
    view_status = status.get(view_index)

    # Cached per session so each rerun costs one get_question call, not two.
    total_cache_key = f"test_total_questions_{session_id}"
    if total_cache_key not in st.session_state:
        probe = get_question(session_id, 0)
        if probe.get("success"):
            st.session_state[total_cache_key] = probe.get("total_questions", 36)
    total_questions = st.session_state.get(total_cache_key, 36)

    if is_frontier and frontier_index >= total_questions:
        # Every question has been opened. Nothing finishes automatically -
        # the learner ends the exam with "Submit All Answers" - so keep a
        # question on screen: the first one still unanswered, else the last.
        remaining = [i for i in range(total_questions) if status.get(i) != "answered"]
        if remaining:
            st.warning(
                f"You've gone through all {total_questions} questions, but "
                f"{len(remaining)} are still unanswered. Answer them from the "
                "Question Navigator, or click Submit All Answers to finish now."
            )
            view_index = remaining[0]
        else:
            st.success(
                "All questions answered. You can still review or change any answer - "
                "click Submit All Answers when you're done."
            )
            view_index = total_questions - 1
        view_status = status.get(view_index)

    # Get current question
    question_result = get_question(session_id, view_index)
    if not question_result.get("success"):
        st.error("Failed to load question")
        return

    # Question data is at root level of response (not nested under "question" key)
    total_questions = question_result.get("total_questions", total_questions)
    question_number = question_result.get("question_number", view_index + 1)
    question_text = question_result.get("question_text", "")
    unit = question_result.get("unit", "")
    bloom_level = question_result.get("bloom_level", "")
    choices = question_result.get("choices", [])

    topbar_col, exit_col = st.columns([5, 1])
    with topbar_col:
        st.markdown(
            f"""
            <div class="gm-exam-topbar">
                <div class="gm-exam-topbar-fields">
                    <div class="gm-exam-field">
                        <span class="gm-exam-field-k">Unit Competency</span>
                        <span class="gm-exam-field-v">{unit}</span>
                    </div>
                    <div class="gm-exam-field">
                        <span class="gm-exam-field-k">Bloom Level</span>
                        <span class="gm-exam-level-chip">{bloom_level}</span>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with exit_col:
        answered_count = sum(1 for v in status.values() if v == "answered")
        unanswered_count = total_questions - answered_count

        def _exit_exam():
            st.session_state.test_started = False
            st.session_state.test_current_question = 0
            st.session_state.test_session_id = None
            st.session_state.test_question_status = {}
            st.session_state.test_question_answers = {}
            st.session_state.test_view_index = None
            st.session_state.current_page = "data_analytics"
            return None

        def _submit_all():
            result = complete_quiz(session_id)
            if not result.get("success"):
                return result.get("error") or "Could not submit your answers. Please try again."
            st.session_state.test_completed = True
            st.session_state.test_result = result
            st.session_state.test_view_index = None
            return None

        if st.button("Exit Exam", use_container_width=True, key="test_exit_top"):
            confirm_exam_action(
                "Exit without scoring?",
                "Nothing will be scored or saved, and you will need to start the Test again from question 1.",
                "Yes, exit",
                _exit_exam,
            )
        if st.button("Submit All Answers", use_container_width=True, key="test_submit_all_top"):
            if unanswered_count:
                detail = (
                    f"You have answered {answered_count} of {total_questions} questions. "
                    f"The {unanswered_count} unanswered question(s) will be scored as incorrect."
                )
            else:
                detail = f"You have answered all {total_questions} questions."
            confirm_exam_action(
                "Submit all answers?",
                detail + " Your Test will be scored now and you can't change answers afterward. The Test can only be taken once, so this result is final.",
                "Yes, submit",
                _submit_all,
            )

    # Progress bar
    progress_percentage = min(frontier_index, total_questions) / total_questions
    st.markdown(
        f"""
        <div class="gm-exam-progress-wrap">
            <div class="gm-exam-progress-label">Question {question_number} of {total_questions}</div>
            <div class="gm-exam-progress-track">
                <div class="gm-exam-progress-fill" style="width:{progress_percentage * 100:.1f}%"></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if not is_frontier:
        note = "You already answered this question - you can change your answer below." if view_status == "answered" else "You skipped this question earlier. You can answer it now."
        back_col1, back_col2 = st.columns([4, 1])
        with back_col1:
            st.info(note)
        with back_col2:
            if st.button("Back to Current", use_container_width=True, key="test_back_to_current"):
                st.session_state.test_view_index = None
                st.rerun()

    main_col, nav_col = st.columns([3, 1.1])

    with main_col:
        with st.container(key="gm_exam_question_card"):
            if view_status == "answered":
                st.markdown('<span class="gm-question-answered-marker"></span>', unsafe_allow_html=True)
            st.markdown(f"**Question {question_number}**")
            st.write(f"### {question_text}")

            # Answer options
            if not choices:
                st.warning("No answer choices available")
                return

            # Create choice text with letters
            choice_options = [f"{choice.get('id')}. {choice.get('text')}" for choice in choices]

            # Pre-select whatever was previously chosen (if anything), so
            # revisiting an answered question shows - and lets the learner
            # change - their existing answer instead of starting blank.
            previous_choice = st.session_state.test_question_answers.get(view_index)
            preselect_idx = None
            if previous_choice:
                for i, opt in enumerate(choice_options):
                    if opt.split(".")[0] == previous_choice:
                        preselect_idx = i
                        break

            # Store selected answer
            selected_text = st.radio(
                label="Select your answer:",
                options=choice_options,
                key=f"test_question_{view_index}",
                index=preselect_idx,
            )

            st.divider()
            col1, col2 = st.columns(2)

            with col1:
                submit_disabled = not selected_text
                if st.button("Submit Answer", use_container_width=True, type="primary", disabled=submit_disabled):
                    selected_choice_id = selected_text.split(".")[0]  # Extract letter (A, B, C, D)
                    submit_result = submit_answer(
                        session_id,
                        view_index,
                        selected_choice_id
                    )

                    if submit_result.get("success"):
                        status[view_index] = "answered"
                        st.session_state.test_question_answers[view_index] = selected_choice_id
                        if is_frontier:
                            st.session_state.test_current_question = frontier_index + 1
                        st.session_state.test_view_index = None
                        st.rerun()
                    else:
                        st.error(f"Failed to submit answer: {submit_result.get('error')}")

            with col2:
                if view_status != "answered" and st.button("Skip", use_container_width=True, key="test_skip_btn"):
                    status[view_index] = "skipped"
                    if is_frontier:
                        st.session_state.test_current_question = frontier_index + 1
                    st.session_state.test_view_index = None
                    st.rerun()

    with nav_col:
        render_exam_navigator(
            total_questions, status, frontier_index + 1, view_index + 1,
            key_prefix="test", view_state_key="test_view_index",
        )


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

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("Go to Practice", use_container_width=True, type="primary"):
            st.session_state.test_started = False
            st.session_state.test_current_question = 0
            st.session_state.test_session_id = None
            st.session_state.test_completed = False
            st.session_state.test_result = None
            st.session_state.test_question_status = {}
            st.session_state.test_question_answers = {}
            st.session_state.test_view_index = None
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
            st.session_state.test_question_status = {}
            st.session_state.test_question_answers = {}
            st.session_state.test_view_index = None
            st.session_state.current_page = "profile"
            st.rerun()

    with col4:
        if st.button("Exit Exam", use_container_width=True):
            st.session_state.test_started = False
            st.session_state.test_current_question = 0
            st.session_state.test_session_id = None
            st.session_state.test_completed = False
            st.session_state.test_result = None
            st.session_state.test_question_status = {}
            st.session_state.test_question_answers = {}
            st.session_state.test_view_index = None
            st.session_state.current_page = "data_analytics"
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
