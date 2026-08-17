"""
Bookmark notes module (used by Learning Path -> Cue Questions -> "Cue
Question" tab, and Learning Path -> Key Points -> "Materials"/"Chat" tabs).

Two public entry points:
  - render_save_button(...): a reusable Save-to-Notes / Remove-from-Notes toggle
    dropped into any supported content (Reading Materials, Practice Questions,
    Chatbot Discussions). Imported by those components directly, so they stay
    independent of wherever bookmarks are actually browsed.
  - render_bookmarks(source_type): the saved-bookmarks list for ONE source
    type (Materials, Questions, or Chat) - each note showing source type,
    snapshot content, created date, an "Open source" action, and a "Remove
    note" action. Composed into tabs by components/cue_questions.py (Question
    bookmarks) and components/key_points.py (Material/Chat bookmarks) -
    there is no single combined "Notes" page anymore; this module only owns
    the reusable bookmark pieces.

All persistence goes through utils/notes_api.py -> /api/notes/* (its own
user_notes table); nothing here reads or writes any other module's data.
"""

from datetime import datetime

import streamlit as st

from utils.notes_api import (
    save_note, remove_note, list_notes, get_saved_source_ids,
    SOURCE_MATERIAL, SOURCE_QUESTION, SOURCE_CHAT,
)

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


def render_bookmarks(source_type: str):
    """Render the saved bookmarks for a single source type. Each note shows
    its snapshot, created date, an Open-source action, and a Remove action."""
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
