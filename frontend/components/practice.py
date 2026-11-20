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
from utils.notes_api import get_saved_source_ids, SOURCE_QUESTION
from utils.theme import render_exam_navigator, confirm_exam_action
from components.notes import render_save_button


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
    if "practice_question_status" not in st.session_state:
        # 0-based question index -> "answered" | "skipped". Any index not in
        # here, below the frontier (practice_current_question), was visited
        # but has no explicit status yet (shouldn't normally happen); above
        # the frontier it simply hasn't been opened.
        st.session_state.practice_question_status = {}
    if "practice_view_index" not in st.session_state:
        # Which question is on screen right now. None means "whatever the
        # frontier is" - set explicitly only when the learner jumps to an
        # earlier (skipped/answered) question via the Question Navigator.
        st.session_state.practice_view_index = None
    if "practice_question_answers" not in st.session_state:
        # 0-based question index -> previously selected choice letter, so
        # revisiting an answered question pre-selects what was chosen
        # before (and lets the learner change it - submit_answer upserts
        # by index server-side, so resubmitting never double-counts).
        st.session_state.practice_question_answers = {}


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
    """Render practice in progress.

    `practice_current_question` is the FRONTIER - the furthest index ever
    reached by forward (Submit/Skip) progression. `practice_view_index`
    is what's actually on screen right now; it's None (meaning "= the
    frontier") unless the learner jumped to an earlier skipped/answered
    question via the Question Navigator. Jumping is always safe: viewing
    an already-answered question is read-only (no re-submit, so the
    backend's answers list never gets a duplicate entry for that index);
    viewing a skipped question allows a real, first-time Submit for it.
    """
    session_id = st.session_state.practice_session_id
    frontier_index = st.session_state.practice_current_question
    status = st.session_state.practice_question_status

    view_index = st.session_state.practice_view_index
    if view_index is None:
        view_index = frontier_index
    is_frontier = view_index == frontier_index
    view_status = status.get(view_index)

    # Probe total_questions without assuming the frontier index is still
    # in range (it won't be once every question has been visited at least
    # once, via answer or skip, but some were only skipped).
    # Cached per session so each rerun costs one get_question call, not two.
    total_cache_key = f"practice_total_questions_{session_id}"
    if total_cache_key not in st.session_state:
        probe = get_question(session_id, 0)
        if probe.get("success"):
            st.session_state[total_cache_key] = probe.get("total_questions", 1)
    total_questions = st.session_state.get(total_cache_key, 1)

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

    question_result = get_question(session_id, view_index)
    if not question_result.get("success"):
        st.error("Failed to load question")
        return

    total_questions = question_result.get("total_questions", total_questions)
    question_number = question_result.get("question_number", view_index + 1)
    question_text = question_result.get("question_text", "")
    unit = question_result.get("unit", "")
    bloom_level = question_result.get("bloom_level", "")
    choices = question_result.get("choices", [])
    question_id = question_result.get("question_id")

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
            st.session_state.practice_started = False
            st.session_state.practice_current_question = 0
            st.session_state.practice_session_id = None
            st.session_state.practice_question_status = {}
            st.session_state.practice_question_answers = {}
            st.session_state.practice_view_index = None
            st.session_state.current_page = "data_analytics"
            return None

        def _submit_all():
            result = complete_practice(session_id)
            if not result.get("success"):
                return result.get("error") or "Could not submit your answers. Please try again."
            st.session_state.practice_completed = True
            st.session_state.practice_result = result
            st.session_state.practice_view_index = None
            return None

        if st.button("Exit Exam", use_container_width=True, key="practice_exit_top"):
            confirm_exam_action(
                "Exit without scoring?",
                "Nothing will be scored or saved, and this Practice session will be discarded.",
                "Yes, exit",
                _exit_exam,
            )
        if st.button("Submit All Answers", use_container_width=True, key="practice_submit_all_top"):
            if unanswered_count:
                detail = (
                    f"You have answered {answered_count} of {total_questions} questions. "
                    f"The {unanswered_count} unanswered question(s) will be scored as incorrect."
                )
            else:
                detail = f"You have answered all {total_questions} questions."
            confirm_exam_action(
                "Submit all answers?",
                detail + " Your Practice will be scored now and you can't change answers afterward.",
                "Yes, submit",
                _submit_all,
            )

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
            if st.button("Back to Current", use_container_width=True, key="practice_back_to_current"):
                st.session_state.practice_view_index = None
                st.rerun()

    main_col, nav_col = st.columns([3, 1.1])

    with main_col:
        with st.container(key="gm_exam_question_card"):
            if view_status == "answered":
                st.markdown('<span class="gm-question-answered-marker"></span>', unsafe_allow_html=True)
            st.markdown(f"**Question {question_number}**")
            st.write(f"### {question_text}")

            if not choices:
                st.warning("No answer choices available")
                return

            choice_options = [f"{choice.get('id')}. {choice.get('text')}" for choice in choices]

            # Pre-select whatever was previously chosen (if anything), so
            # revisiting an answered question shows - and lets the learner
            # change - their existing answer instead of starting blank.
            previous_choice = st.session_state.practice_question_answers.get(view_index)
            preselect_idx = None
            if previous_choice:
                for i, opt in enumerate(choice_options):
                    if opt.split(".")[0] == previous_choice:
                        preselect_idx = i
                        break

            selected_text = st.radio(
                label="Select your answer:",
                options=choice_options,
                key=f"practice_question_{view_index}",
                index=preselect_idx,
            )

            st.divider()
            col1, col2, col3 = st.columns(3)

            with col1:
                submit_disabled = not selected_text
                if st.button("Submit Answer", use_container_width=True, type="primary", disabled=submit_disabled):
                    selected_choice_id = selected_text.split(".")[0]
                    submit_result = submit_answer(session_id, view_index, selected_choice_id)

                    if submit_result.get("success"):
                        status[view_index] = "answered"
                        st.session_state.practice_question_answers[view_index] = selected_choice_id
                        if is_frontier:
                            st.session_state.practice_current_question = frontier_index + 1
                        st.session_state.practice_view_index = None
                        st.rerun()
                    else:
                        st.error(f"Failed to submit answer: {submit_result.get('error')}")

            with col2:
                if view_status != "answered" and st.button("Skip", use_container_width=True, key="practice_skip_btn"):
                    status[view_index] = "skipped"
                    if is_frontier:
                        st.session_state.practice_current_question = frontier_index + 1
                    st.session_state.practice_view_index = None
                    st.rerun()

            with col3:
                if question_id:
                    saved_q_ids = get_saved_source_ids(SOURCE_QUESTION)
                    snapshot = question_text + "\n\n" + "\n".join(f"- {opt}" for opt in choice_options)
                    render_save_button(
                        SOURCE_QUESTION, str(question_id), snapshot,
                        title=f"{unit} · {bloom_level}",
                        source_ref={"unit": unit, "bloom_level": bloom_level, "question_text": question_text},
                        saved_ids=saved_q_ids, key=f"note_q_{question_id}",
                    )

    with nav_col:
        render_exam_navigator(
            total_questions, status, frontier_index + 1, view_index + 1,
            key_prefix="practice", view_state_key="practice_view_index",
        )


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
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("Practice Again", use_container_width=True, type="primary"):
            st.session_state.practice_started = False
            st.session_state.practice_current_question = 0
            st.session_state.practice_session_id = None
            st.session_state.practice_completed = False
            st.session_state.practice_result = None
            st.session_state.practice_show_review = False
            st.session_state.practice_question_status = {}
            st.session_state.practice_question_answers = {}
            st.session_state.practice_view_index = None
            st.rerun()

    with col2:
        review_label = "📋 Hide Practice Review" if st.session_state.practice_show_review else "View Practice Review"
        if st.button(review_label, use_container_width=True):
            st.session_state.practice_show_review = not st.session_state.practice_show_review
            st.rerun()

    with col3:
        if st.button("Back to Learning Path", use_container_width=True):
            st.session_state.practice_started = False
            st.session_state.practice_current_question = 0
            st.session_state.practice_session_id = None
            st.session_state.practice_completed = False
            st.session_state.practice_result = None
            st.session_state.practice_show_review = False
            st.session_state.practice_question_status = {}
            st.session_state.practice_question_answers = {}
            st.session_state.practice_view_index = None
            st.session_state.current_page = "learning_path"
            st.rerun()

    with col4:
        if st.button("Exit Exam", use_container_width=True):
            st.session_state.practice_started = False
            st.session_state.practice_current_question = 0
            st.session_state.practice_session_id = None
            st.session_state.practice_completed = False
            st.session_state.practice_result = None
            st.session_state.practice_show_review = False
            st.session_state.practice_question_status = {}
            st.session_state.practice_question_answers = {}
            st.session_state.practice_view_index = None
            st.session_state.current_page = "data_analytics"
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
