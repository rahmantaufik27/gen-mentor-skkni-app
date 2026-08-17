"""
Free Notes module - user-authored WYSIWYG notes.

Public entry point:
  - render_free_notes(category, key_prefix): a WYSIWYG editor (streamlit-quill)
    for writing a new note, plus the list of the user's existing free notes in
    that category, each independently editable and deletable. Used by the
    "Free Question" tab (components/cue_questions.py) and the "Free Notes" tab
    (components/key_points.py) - same component, different category, so the
    create/edit/delete logic isn't duplicated between the two pages.

Backed by /api/free-notes/* (its own user_free_notes table, see
utils/free_notes_api.py) - pure user-authored rich text with no source to
reference, independent of bookmarks (components/notes.py) and the configured
reflection questions (components/reflection_learning.py).
"""

from datetime import datetime

import streamlit as st
from streamlit_quill import st_quill

from utils.free_notes_api import list_free_notes, create_free_note, update_free_note, delete_free_note

# A focused toolbar covering the "basic formatting" the task calls for
# (bold/italic/etc.) rather than Quill's full default toolbar (fonts, images,
# formulas, ...), which would be overkill for a quick personal note.
_BASIC_TOOLBAR = [
    ["bold", "italic", "underline", "strike"],
    [{"list": "ordered"}, {"list": "bullet"}],
    ["clean"],
]

# Quill's placeholder for "empty" content - used to tell a genuinely blank
# note apart from one with real text before allowing Add/Save.
_EMPTY_QUILL_HTML = {"", "<p></p>", "<p><br></p>"}


def _format_date(iso_date: str) -> str:
    if not iso_date:
        return "-"
    try:
        return datetime.fromisoformat(iso_date).strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return iso_date


def _is_blank(html: str) -> bool:
    return (html or "").strip() in _EMPTY_QUILL_HTML


def render_free_notes(category: str, key_prefix: str):
    """Render the "write a new note" editor plus the list of saved free notes
    for this category, each with independent Edit/Save/Delete."""
    with st.container(border=True):
        st.markdown("##### New Note")
        new_content = st_quill(
            value="", html=True, toolbar=_BASIC_TOOLBAR,
            placeholder="Write a note…", key=f"{key_prefix}_quill_new",
        )
        if st.button("➕ Add Note", key=f"{key_prefix}_add_btn", type="primary"):
            if _is_blank(new_content):
                st.toast("Write something before adding a note", icon="⚠️")
            else:
                result = create_free_note(category, new_content)
                if result.get("success"):
                    st.toast("Note added")
                    st.rerun()
                else:
                    st.toast(f"Could not add note: {result.get('error', 'error')}", icon="⚠️")

    result = list_free_notes(category)
    if not result.get("success"):
        st.error(f"Failed to load notes: {result.get('error', 'Unknown error')}")
        return

    notes = result.get("notes", [])
    if not notes:
        st.info("No notes here yet - write one above.")
        return

    st.markdown("")
    for note in notes:
        note_id = note["id"]
        editing_key = f"{key_prefix}_editing_{note_id}"

        with st.container(border=True):
            st.caption(f"Updated {_format_date(note.get('updated_at') or note.get('created_at'))}")

            if st.session_state.get(editing_key):
                edited_content = st_quill(
                    value=note.get("content_html", ""), html=True, toolbar=_BASIC_TOOLBAR,
                    key=f"{key_prefix}_quill_edit_{note_id}",
                )
                save_col, cancel_col = st.columns(2)
                with save_col:
                    if st.button("💾 Save", key=f"{key_prefix}_save_{note_id}", type="primary", use_container_width=True):
                        if _is_blank(edited_content):
                            st.toast("Note can't be empty", icon="⚠️")
                        else:
                            res = update_free_note(note_id, edited_content)
                            if res.get("success"):
                                st.session_state[editing_key] = False
                                st.toast("Note updated")
                                st.rerun()
                            else:
                                st.toast(f"Could not save: {res.get('error', 'error')}", icon="⚠️")
                with cancel_col:
                    if st.button("✕ Cancel", key=f"{key_prefix}_cancel_{note_id}", use_container_width=True):
                        st.session_state[editing_key] = False
                        st.rerun()
            else:
                st.markdown(note.get("content_html", ""), unsafe_allow_html=True)
                edit_col, delete_col = st.columns(2)
                with edit_col:
                    if st.button("Edit", key=f"{key_prefix}_edit_{note_id}", use_container_width=True):
                        st.session_state[editing_key] = True
                        st.rerun()
                with delete_col:
                    if st.button("Delete", key=f"{key_prefix}_delete_{note_id}", use_container_width=True):
                        res = delete_free_note(note_id)
                        if res.get("success"):
                            st.toast("Note deleted")
                            st.rerun()
                        else:
                            st.toast(f"Could not delete: {res.get('error', 'error')}", icon="⚠️")
