"""
Key Points module (Learning Path -> Key Points).

Self-contained module: exposes render_key_points() as its only public entry
point - three tabs:
  - "Materials": saved Reading Material bookmarks (moved here from the former
    Notes page's "Materials" tab, unchanged).
  - "Chat": saved Chatbot Discussion bookmarks (moved here from the former
    Notes page's "Chat" tab, unchanged).
  - "Free Notes": user-authored WYSIWYG notes (new) - see
    components/free_notes.py::render_free_notes / utils/free_notes_api.py.
"""

import streamlit as st

from components.notes import render_bookmarks
from utils.notes_api import SOURCE_MATERIAL, SOURCE_CHAT
from components.free_notes import render_free_notes
from utils.free_notes_api import CATEGORY_KEY_POINTS


def render_key_points():
    """Render the Key Points page: Materials + Chat (bookmarks) + Free Notes (WYSIWYG)."""
    tab_materials, tab_chat, tab_free = st.tabs(["📄 Materials", "💬 Chat", "🗒️ Free Notes"])
    with tab_materials:
        render_bookmarks(SOURCE_MATERIAL)
    with tab_chat:
        render_bookmarks(SOURCE_CHAT)
    with tab_free:
        render_free_notes(CATEGORY_KEY_POINTS, key_prefix="kp_free")
