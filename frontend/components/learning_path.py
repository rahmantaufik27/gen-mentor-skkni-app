"""
Learning Path orchestrator.

Presents the available learning methods and delegates rendering to each
method's own component. Adding a new learning method later only requires
adding an entry to LEARNING_METHODS and its own render_* component - no
changes needed to existing methods (e.g. components/reading_materials.py)
or to the selector logic below.
"""

import streamlit as st

from components.reading_materials import render_reading_materials


def _render_coming_soon(name: str, description: str):
    """Placeholder renderer for a learning method that hasn't been built yet."""
    def _render():
        st.info(f"**{name}** is coming soon. {description}")
    return _render


LEARNING_METHODS = {
    "reading_materials": {"label": "📖 Reading Materials", "render": render_reading_materials},
    # Placeholders below show how a future method plugs in: add a real
    # component (see components/reading_materials.py for the pattern) and
    # point "render" at it - no changes needed to Reading Materials or the
    # selector logic below.
    "video_tutorials": {
        "label": "🤖 Learning with Chatbot Assistance",
        "render": _render_coming_soon("Video Tutorials", "Step-by-step video guides for each unit."),
    },
    # "practice_exercises": {
    #     "label": "🛤️ Tracking Progress Learning",
    #     "render": _render_coming_soon("Practice Exercises", "Interactive exercises to reinforce your learning."),
    # },
}


def render_learning_path():
    """Render the Learning Path page: a method selector + the active method's content."""
    method_keys = list(LEARNING_METHODS.keys())
    labels = [LEARNING_METHODS[key]["label"] for key in method_keys]

    if st.session_state.get("learning_method") not in method_keys:
        st.session_state["learning_method"] = method_keys[0]

    selected_label = st.radio(
        "Learning method",
        options=labels,
        index=method_keys.index(st.session_state["learning_method"]),
        horizontal=True,
        label_visibility="collapsed",
        key="learning_method_selector",
    )
    st.session_state["learning_method"] = method_keys[labels.index(selected_label)]
    st.markdown("")

    LEARNING_METHODS[st.session_state["learning_method"]]["render"]()
