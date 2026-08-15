"""
Notes learning method (Learning Path -> Notes).

Two public entry points:
  - render_save_button(...): a reusable Save-to-Notes / Remove-from-Notes toggle
    dropped into any supported content (Reading Materials, Practice Questions,
    Chatbot Discussions). It's the ONLY thing those components import from here,
    so Notes stays modular and they stay independent of the Notes page itself.
  - render_notes(): the Notes page - tabs for Free Notes (the "Cue Questions &
    Key Points" reflection prompts) plus one tab per bookmark source type
    (Materials, Questions, Chat), each bookmark showing source type, snapshot
    content, created date, an "Open source" action, and a "Remove note" action.

Bookmark persistence goes through utils/notes_api.py -> /api/notes/* (its own
user_notes table). The Free Notes tab's Cue Questions form is rendered via
components/reflection_learning.py::render_reflection_form(), which owns the
reflection question logic - the Reflection & Action Plan section lives on its
own "Reflection Learning" page (see pages/reflection_learning.py), sharing the
same backend/table so no reflection data is duplicated or lost.
"""

from datetime import datetime

import streamlit as st

from utils.notes_api import (
    save_note, remove_note, list_notes, get_saved_source_ids,
    SOURCE_MATERIAL, SOURCE_QUESTION, SOURCE_CHAT,
)
from components.reflection_learning import render_reflection_form

# Display metadata per source type - label + icon, in one place so the toggle,
# the filter, and the note cards all stay consistent.
SOURCE_META = {
    SOURCE_MATERIAL: {"label": "Material", "icon": "📄"},
    SOURCE_QUESTION: {"label": "Question", "icon": "❓"},
    SOURCE_CHAT: {"label": "Chat", "icon": "💬"},
}


def _format_date(iso_date: str) -> str:
    if not iso_date:
        return "-"
    try:
        return datetime.fromisoformat(iso_date).strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return iso_date


def render_save_button(source_type, source_id, snapshot_text, title=None, source_ref=None, saved_ids=None, key=None):
    """
    Reusable Save-to-Notes / Remove-from-Notes toggle for one piece of content.

    Args:
        source_type: SOURCE_MATERIAL | SOURCE_QUESTION | SOURCE_CHAT
        source_id:   stable id of the specific content (material url, question_id,
                     chat message id)
        snapshot_text: the selected/snapshot content stored with the note
        title:       optional short label for the note
        source_ref:  optional JSON-able dict used to open/return to the original
        saved_ids:   set of already-saved source_ids for this source_type (pass
                     from the caller's one-time get_saved_source_ids() so we don't
                     re-query per button); falls back to a lookup if omitted
        key:         unique Streamlit widget key
    """
    if not source_id or not snapshot_text:
        return
    if saved_ids is None:
        saved_ids = get_saved_source_ids(source_type)

    is_saved = source_id in saved_ids
    label = "Remove from Notes" if is_saved else "Save to Notes"

    if st.button(label, key=key, use_container_width=True):
        if is_saved:
            result = remove_note(source_type=source_type, source_id=source_id)
            if result.get("success"):
                st.toast("Removed from Notes")
            else:
                st.toast(f"Could not remove: {result.get('error', 'error')}", icon="⚠️")
        else:
            result = save_note(source_type, source_id, snapshot_text, title=title, source_ref=source_ref)
            if result.get("success"):
                st.toast("Saved to Notes" if result.get("created") else "Already in Notes")
            else:
                st.toast(f"Could not save: {result.get('error', 'error')}", icon="⚠️")
        st.rerun()


def _open_source(note: dict, key: str):
    """Render the note's "Open source" action, adapted to its source type."""
    source_type = note.get("source_type")
    ref = note.get("source_ref") or {}

    if source_type == SOURCE_MATERIAL:
        url = ref.get("url") or note.get("source_id")
        if url and str(url).startswith("http"):
            st.link_button("Open material", url, use_container_width=True)
        else:
            st.button("Open material", key=key, use_container_width=True, disabled=True,
                      help="No link stored for this material")
    elif source_type == SOURCE_QUESTION:
        if st.button("Go to Practice", key=key, use_container_width=True):
            st.session_state.current_page = "practice"
            st.rerun()
    elif source_type == SOURCE_CHAT:
        if st.button("Go to Chatbot", key=key, use_container_width=True):
            st.session_state.current_page = "chatbot"
            st.rerun()


def render_notes():
    """
    Render the Notes page as tabs: Free Notes (the "Cue Questions & Key
    Points" reflection prompts) plus one tab per bookmark source type
    (Materials, Questions, Chat). The Reflection & Action Plan section lives
    on its own "Reflection Learning" page, not here - see
    components/reflection_learning.py.
    """
    tab_free_notes, tab_materials, tab_questions, tab_chat = st.tabs(
        ["🗒️ Free Notes", "📄 Materials", "❓ Questions", "💬 Chat"]
    )
    with tab_free_notes:
        _render_free_notes()
    with tab_materials:
        _render_bookmarks(SOURCE_MATERIAL)
    with tab_questions:
        _render_bookmarks(SOURCE_QUESTION)
    with tab_chat:
        _render_bookmarks(SOURCE_CHAT)


def _render_free_notes():
    """Free Notes tab: the "Cue Questions & Key Points" reflection prompts -
    quick free-text notes to activate prior knowledge before diving in.
    Rendering/persistence is owned by components/reflection_learning.py so
    it's shared, unduplicated logic with the Reflection Learning page."""
    st.caption(
        "Quick notes to activate what you already know before diving in. "
        "Answers are saved to your account and loaded when you return."
    )
    render_reflection_form(["cue_questions"])


def _render_bookmarks(source_type: str):
    """Render the saved bookmarks for a single source type (the existing Notes
    list, now scoped per tab). Each note shows its snapshot, created date, an
    Open-source action, and a Remove action."""
    result = list_notes(source_type)
    if not result.get("success"):
        st.error(f"Failed to load notes: {result.get('error', 'Unknown error')}")
        return

    notes = result.get("notes", [])
    if not notes:
        meta = SOURCE_META.get(source_type, {"label": source_type})
        st.info(f"No {meta['label']} notes yet. Use **Save to Notes** on a {meta['label'].lower()} to add one.")
        return

    for note in notes:
        meta = SOURCE_META.get(note.get("source_type"), {"label": note.get("source_type", "?"), "icon": "•"})
        note_id = note.get("id")
        with st.container(border=True):
            head_col, action_col = st.columns([4, 1])
            with head_col:
                st.markdown(f"**{meta['icon']} {meta['label']}**")
                if note.get("title"):
                    st.markdown(f"*{note['title']}*")
                st.markdown(note.get("snapshot_text", ""))
                st.caption(f"Saved {_format_date(note.get('created_at'))}")
            with action_col:
                _open_source(note, key=f"open_{note_id}")
                if st.button("Remove note", key=f"remove_{note_id}", use_container_width=True):
                    res = remove_note(note_id=note_id)
                    if res.get("success"):
                        st.toast("Note removed")
                        st.rerun()
                    else:
                        st.toast(f"Could not remove: {res.get('error', 'error')}", icon="⚠️")
