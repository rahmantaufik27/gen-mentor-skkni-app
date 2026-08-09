"""
Practice with Generative Questions learning method.

Self-contained module: exposes render_practice() as its only public entry
point. Same interactive UI/UX as Test (question navigation, answer
selection, submission, scoring, progress, results) - see
pages/test.py for the Test equivalent this mirrors - but sourced from
questions recommended for the user's weakest units (the same existing
recommendation flow: backend/services/neo4j_service.py::
get_recommended_questions), via a separate session-based backend
(backend/services/practice_service.py) that never touches
quiz_attempts/user_mastery_level. Test remains the sole source of mastery
truth; Practice is purely for reinforcement.

On completion, a "View Practice Review" button opens, on demand, a Review
Practice section (per-question detail + each covered unit's inferred
Knowledge Level, via the same Manual/DBN strategy Test uses) - not shown
automatically, so the results screen stays focused on the score summary
by default. See _render_practice_review(); the same table layout is also
used by pages/test.py::show_test_history() for Test History's per-attempt
review, so the two stay visually consistent.
"""

import pandas as pd
import streamlit as st

from utils.practice_api import start_practice, get_question, submit_answer, complete_practice
from utils.gating import get_learning_gating
from utils.quiz_api import get_unit_code_map


def _get_code_map() -> dict:
    """Truncated -> full unit_code map (see utils/quiz_api.py::get_unit_code_map and
    components/mastery_dashboard.py's identical helper). Falls back to an empty map on
    failure so callers can always .get(code, code) without special-casing errors."""
    result = get_unit_code_map()
    return result.get("unit_codes", {}) if result.get("success") else {}


def initialize_practice_state():
    """Initialize practice session state"""
    if "practice_session_id" not in st.session_state:
        st.session_state.practice_session_id = None
    if "practice_current_question" not in st.session_state:
        st.session_state.practice_current_question = 0
    if "practice_started" not in st.session_state:
        st.session_state.practice_started = False
    if "practice_completed" not in st.session_state:
        st.session_state.practice_completed = False
    if "practice_result" not in st.session_state:
        st.session_state.practice_result = None
    if "practice_show_review" not in st.session_state:
        st.session_state.practice_show_review = False


def render_practice():
    """Render the Practice page: start screen, in-progress, or results."""
    initialize_practice_state()

    if not st.session_state.practice_started:
        _render_practice_start()
    elif st.session_state.practice_started and not st.session_state.practice_completed:
        _render_practice_progress()
    else:
        _render_practice_results()


def _render_practice_start():
    """
    Render practice start screen. Always visible - eligibility (see
    utils/gating.py) only disables the Start button below, with an inline
    message explaining why; the page and sidebar menu are never hidden.

    Practice is enabled for the rest of the user's lifetime once their
    one-time Test is done (see utils/gating.py - a Test can never be
    retaken), so the only real "not eligible yet" case left is before
    that Test. The "nothing left to practice right now" case (every unit
    Mastered) is handled by the Start button's own click response (see
    PracticeService._no_questions_response), not a pre-click gate here.
    """
    gating = get_learning_gating()

    st.markdown("#### 📝 Start Practice")

    if not gating["practice_enabled"]:
        st.warning("⚠️ Practice unlocks after you complete your Placement Test.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        ##### Practice Information
        - **Question source:** Recommended for your weakest units
        - **Question Types:** Multiple Choice
        - **Time Limit:** No time limit
        - **Scoring:** Not counted toward your mastery status
        """)

    with col2:
        st.info("""
        ✅ **Tips for Success**
        - Practice targets units still Remedial after your latest Practice
          results (or your Test, before your first Practice session)
        - Read each question carefully
        - Practice can be repeated as many times as you like - your Test
          result stays as your one-time baseline
        """)

    st.divider()

    if st.button(
        "Start Practice", use_container_width=True, type="primary",
        key="start_practice_btn", disabled=not gating["practice_enabled"],
    ):
        result = start_practice()

        if result.get("success"):
            st.session_state.practice_session_id = result.get("session_id")
            st.session_state.practice_current_question = 0
            st.session_state.practice_started = True
            st.session_state.practice_completed = False
            st.rerun()
        else:
            st.error(result.get("error", "No practice questions recommended right now."))

    if not gating["practice_enabled"]:
        if st.button("Go to Test", use_container_width=True, key="practice_disabled_go_test"):
            st.session_state.current_page = "test"
            st.rerun()


def _render_practice_progress():
    """Render practice in progress"""
    session_id = st.session_state.practice_session_id
    question_index = st.session_state.practice_current_question

    question_result = get_question(session_id, question_index)
    if not question_result.get("success"):
        st.error("Failed to load question")
        return

    total_questions = question_result.get("total_questions", 1)
    question_number = question_result.get("question_number", question_index + 1)
    question_text = question_result.get("question_text", "")
    unit = question_result.get("unit", "")
    bloom_level = question_result.get("bloom_level", "")
    choices = question_result.get("choices", [])

    progress_percentage = question_number / total_questions
    st.progress(progress_percentage, text=f"Progress: {question_number}/{total_questions} questions")

    st.markdown("")

    with st.container(border=True):
        st.subheader(f"Question {question_number} of {total_questions}")

        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Unit:** {unit}")
        with col2:
            st.write(f"**Bloom Level:** {bloom_level}")

        st.divider()

        st.write(f"### {question_text}")

        if not choices:
            st.warning("No answer choices available")
            return

        choice_options = [f"{choice.get('id')}. {choice.get('text')}" for choice in choices]

        selected_text = st.radio(
            label="Select your answer:",
            options=choice_options,
            key=f"practice_question_{question_number}"
        )

        if selected_text:
            selected_choice_id = selected_text.split(".")[0]

            st.divider()

            col1, col2 = st.columns(2)

            with col1:
                if st.button("Submit Answer", use_container_width=True, type="primary"):
                    submit_result = submit_answer(session_id, question_index, selected_choice_id)

                    if submit_result.get("success"):
                        progress_data = submit_result.get("progress", {})

                        if progress_data.get("answered") >= total_questions:
                            complete_result = complete_practice(session_id)
                            if complete_result.get("success"):
                                st.session_state.practice_completed = True
                                st.session_state.practice_result = complete_result
                                st.rerun()
                        else:
                            st.session_state.practice_current_question += 1
                            st.rerun()
                    else:
                        st.error(f"Failed to submit answer: {submit_result.get('error')}")

            with col2:
                if st.button("Exit Practice", use_container_width=True):
                    st.session_state.practice_started = False
                    st.session_state.practice_current_question = 0
                    st.session_state.practice_session_id = None
                    st.rerun()


def _render_practice_results():
    """
    Render practice results. The Review Practice section (per-question
    review + per-unit inferred Knowledge Level) is NOT shown automatically -
    it's opened on demand via the "View Practice Review" button, so the
    results screen stays focused on the score summary by default.
    """
    result_data = st.session_state.practice_result or {}

    st.subheader("Practice Complete!")

    with st.container(border=True):
        col1, col2, col3 = st.columns(3)

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
            st.metric("Total Points", f"{total_score}")

        with col3:
            st.metric("Max Possible", f"{max_score}")

        st.success("Nice work! Keep practicing to strengthen these units, then try a Test when you're ready.")

    st.markdown("")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Practice Again", use_container_width=True, type="primary"):
            st.session_state.practice_started = False
            st.session_state.practice_current_question = 0
            st.session_state.practice_session_id = None
            st.session_state.practice_completed = False
            st.session_state.practice_result = None
            st.session_state.practice_show_review = False
            st.rerun()

    with col2:
        review_label = "📋 Hide Practice Review" if st.session_state.practice_show_review else "View Practice Review"
        if st.button(review_label, use_container_width=True):
            st.session_state.practice_show_review = not st.session_state.practice_show_review
            st.rerun()

    with col3:
        if st.button("Back to Dashboard", use_container_width=True):
            st.session_state.practice_started = False
            st.session_state.practice_current_question = 0
            st.session_state.practice_session_id = None
            st.session_state.practice_completed = False
            st.session_state.practice_result = None
            st.session_state.practice_show_review = False
            st.session_state.current_page = "profile"
            st.rerun()

    if st.session_state.practice_show_review:
        _render_practice_review(result_data)


def _render_practice_review(result_data: dict):
    """
    Review Practice: each unit's inferred Knowledge Level this session
    (Manual or DBN, per the user's inference_method - see
    PracticeService._save_practice_attempt), then the per-question detail
    table (Question No. / Unit / Question Knowledge Level / User Answer /
    Result). Units are displayed with their full code (e.g.
    "J.620100.005.02") for consistency with the rest of the app.
    """
    code_map = _get_code_map()

    with st.container(border=True):
        st.markdown("#### 📋 Review Practice")

        unit_mastery = result_data.get("unit_mastery", {})
        if unit_mastery:
            st.markdown("###### Inferred Knowledge Level per Unit")
            level_df = pd.DataFrame([
                {"Unit": code_map.get(unit_code, unit_code), "Inferred Knowledge Level": level or "-"}
                for unit_code, level in unit_mastery.items()
            ])
            st.dataframe(level_df, use_container_width=True, hide_index=True)
            st.markdown("")

        review = result_data.get("review", [])
        if review:
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
