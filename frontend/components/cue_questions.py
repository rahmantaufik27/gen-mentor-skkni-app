"""
Cue Questions module (Learning Path -> Cue Questions).

Self-contained module: exposes render_cue_questions() as its only public
entry point - two tabs:
  - "Cue Question": saved Practice Question bookmarks (moved here from the
    former Notes page's "Questions" tab, unchanged - see
    components/notes.py::render_bookmarks / utils/notes_api.py).
  - "Free Question": user-authored WYSIWYG notes about questions (new) - see
    components/free_notes.py::render_free_notes / utils/free_notes_api.py.
"""

import streamlit as st

from components.notes import render_bookmarks
from utils.notes_api import SOURCE_QUESTION
from components.free_notes import render_free_notes
from utils.free_notes_api import CATEGORY_QUESTION


def render_cue_questions():
    """Render the Cue Questions page: Cue Question (bookmarks) + Free Question (WYSIWYG)."""
    tab_cue, tab_free = st.tabs(["❓ Cue Question", "✏️ Free Question"])
    with tab_cue:
        render_bookmarks(SOURCE_QUESTION)
    with tab_free:
        render_free_notes(CATEGORY_QUESTION, key_prefix="cue_free_q")
