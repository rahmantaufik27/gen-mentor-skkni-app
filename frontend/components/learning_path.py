"""
Learning Path module.

LEARNING_METHODS is the single source of truth for the three Learning Path
sub-features (Reading Materials, Learning with Chatbot Assistance,
Practice with Generative Questions): their sidebar submenu labels (via
get_learning_path_submenu()) and their render functions. Each method is now
its own dedicated full page (pages/reading_materials.py, pages/chatbot.py,
pages/practice.py) rather than content switched inside Learning Path -
Learning Path itself is a separate landing page (pages/learning_path.py).

Practice's Start button is enabled/disabled based on Test eligibility - see
utils/gating.py (components/practice.py enforces it; the menu entry itself
always stays visible/clickable).

Adding a new learning method later: add an entry to LEARNING_METHODS,
create its own pages/<name>.py (follow the existing pattern - see any of
the three above), and add one elif branch to
pages/learner_profile.py's routing - no changes needed to the other
methods or to the sidebar.
"""

import streamlit as st

from components.reading_materials import render_reading_materials
from components.practice import render_practice


def _render_coming_soon(name: str, description: str):
    """Placeholder renderer for a learning method that hasn't been built yet."""
    def _render():
        st.info(f"**{name}** is coming soon. {description}")
    return _render


LEARNING_METHODS = {
    "reading_materials": {"label": "Reading Materials", "render": render_reading_materials},
    "chatbot": {
        "label": "Learning with Chatbot Assistance",
        "render": _render_coming_soon(
            "Learning with Chatbot Assistance",
            "Chat with an AI tutor for personalized help - LLM integration coming soon.",
        ),
    },
    "practice": {"label": "Practice with Generative Questions", "render": render_practice},
}


def get_learning_path_submenu() -> list:
    """Sidebar submenu items for Learning Path, derived from LEARNING_METHODS."""
    return [{"key": key, "label": method["label"]} for key, method in LEARNING_METHODS.items()]
