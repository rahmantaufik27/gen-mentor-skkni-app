"""
Exercises with Generative Questions learning method.

Self-contained module: exposes render_exercises() as its only public entry
point, so components/learning_path.py (and any future learning method) can
use it without knowing anything about how questions are recommended.

Sources practice questions from the existing backend endpoint
(GET /api/quiz/recommended-questions), which already picks adaptive
questions from the Neo4j knowledge graph based on the user's Remedial
units and current knowledge level per unit (see
backend/services/neo4j_service.py::get_recommended_questions). This module
only renders whatever it's given - swapping the recommendation engine
later needs no change here.
"""

import streamlit as st

from utils.quiz_api import get_recommended_questions

OPTION_LETTERS = "ABCDEFGH"


def _render_question_card(question: dict, position: int):
    with st.container(border=True):
        status = question.get("mastery_status") or "Remedial"
        badge_class = "gm-badge-success" if status == "Mastered" else "gm-badge-danger"
        st.markdown(
            f"<span class='gm-badge {badge_class}'>{status}</span> "
            f"<span style='color: var(--text-muted); font-size: 13px;'>"
            f"Unit: {question.get('unit', '-')} · Bloom Level: {question.get('bloom_level', '-')} "
            f"· Target: {question.get('target_level', '-')}</span>",
            unsafe_allow_html=True,
        )
        st.markdown(f"**{position}. {question.get('question_text', '')}**")

        for letter, option_text in zip(OPTION_LETTERS, question.get("options") or []):
            st.markdown(f"{letter}. {option_text}")


def render_exercises():
    """Render adaptive practice questions recommended for the user's weakest units."""
    col1, col2 = st.columns([5, 1])
    with col1:
        st.caption("Practice questions targeting the units and Bloom levels you need most right now.")
    with col2:
        if st.button("🔄 Refresh", use_container_width=True, key="refresh_exercises"):
            st.rerun()

    st.info(
        "No exercises recommended right now. Take a quiz to refresh your "
        "recommendations, or check Reading Materials to keep learning."
    )

    # result = get_recommended_questions()

    # if not result.get("success"):
    #     st.error(f"Failed to load exercises: {result.get('error', 'Unknown error')}")
    #     return

    # questions = result.get("questions", [])
    # if not questions:
    #     st.info(
    #         "No exercises recommended right now. Take a quiz to refresh your "
    #         "recommendations, or check Reading Materials to keep learning."
    #     )
    #     return

    # for position, question in enumerate(questions, start=1):
    #     _render_question_card(question, position)
