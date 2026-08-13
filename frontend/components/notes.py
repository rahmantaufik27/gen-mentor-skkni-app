"""
Notes learning method (Learning Path -> Notes).

Two public entry points:
  - render_save_button(...): a reusable Save-to-Notes / Remove-from-Notes toggle
    dropped into any supported content (Reading Materials, Practice Questions,
    Chatbot Discussions). It's the ONLY thing those components import from here,
    so Notes stays modular and they stay independent of the Notes page itself.
  - render_notes(): the Notes page - the user's saved notes with a source-type
    filter, each showing source type, snapshot content, created date, an
    "Open source" action, and a "Remove note" action.

All persistence goes through utils/notes_api.py -> /api/notes/* (its own
user_notes table); nothing here reads or writes any other module's data.
"""

from datetime import datetime

import streamlit as st

from utils.notes_api import (
    save_note, remove_note, list_notes, get_saved_source_ids,
    SOURCE_MATERIAL, SOURCE_QUESTION, SOURCE_CHAT,
)
from utils.reflection_api import (
    get_reflection_questions, get_reflection_answers,
    save_reflection_answer, delete_reflection_answer,
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
            st.link_button("🔗 Open material", url, use_container_width=True)
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
    Render the Notes page as tabs: a Learning Reflection tab (structured
    reflection questions) plus one tab per bookmark source type (Materials,
    Questions, Chat). The former "All" bookmark filter is replaced by the
    Learning Reflection tab; the bookmark functionality itself is unchanged,
    just organized per source.
    """
    tab_reflection, tab_materials, tab_questions, tab_chat = st.tabs(
        ["📝 Learning Reflection", "📄 Materials", "❓ Questions", "💬 Chat"]
    )
    with tab_reflection:
        _render_learning_reflection()
    with tab_materials:
        _render_bookmarks(SOURCE_MATERIAL)
    with tab_questions:
        _render_bookmarks(SOURCE_QUESTION)
    with tab_chat:
        _render_bookmarks(SOURCE_CHAT)


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
                if st.button("🗑️ Remove note", key=f"remove_{note_id}", use_container_width=True):
                    res = remove_note(note_id=note_id)
                    if res.get("success"):
                        st.toast("Note removed")
                        st.rerun()
                    else:
                        st.toast(f"Could not remove: {res.get('error', 'error')}", icon="⚠️")


# ---------------------------------------------------------------------------
# Learning Reflection
#
# Questions come from the backend config (data/reflection_questions.json) - only
# their stable question_key is ever stored with an answer, so the wording can
# change without orphaning saved answers. Answers load from the DB on entry and
# each one can be created, edited, and deleted independently.
# ---------------------------------------------------------------------------

def _render_learning_reflection():
    """Render the Learning Reflection tab: config-driven sections of questions,
    each with its saved answer loaded. A SINGLE Save button at the very end of
    the whole form saves/updates every answer in one go (and clears any answer
    the user emptied), rather than per-question controls."""
    st.caption(
        "Reflect on your learning. Answers are saved to your account and loaded "
        "when you return - fill in the form and save it all at once at the bottom."
    )

    questions = get_reflection_questions()
    if not questions.get("success"):
        st.error(f"Failed to load reflection questions: {questions.get('error', 'Unknown error')}")
        return

    answers_result = get_reflection_answers()
    if not answers_result.get("success"):
        st.error(f"Failed to load your reflections: {answers_result.get('error', 'Unknown error')}")
        return
    answers = answers_result.get("answers", {})

    for section in questions.get("sections", []):
        with st.container(border=True):
            st.markdown(f"##### {section.get('title', '')}")
            if section.get("description"):
                st.caption(section["description"])
            for question in section.get("questions", []):
                _render_reflection_question(question, answers.get(question["key"]))

    # --- Single action button for the whole form -------------------------
    has_any_saved = bool(answers)
    st.markdown("")
    save_col, _ = st.columns([1, 2])
    with save_col:
        button_label = "Update Reflection" if has_any_saved else "Save Reflection"
        if st.button(button_label, type="primary", use_container_width=True, key="refl_save_all"):
            _save_all_reflections(questions.get("sections", []), answers)


def _save_all_reflections(sections: list, answers: dict):
    """Persist every answer in the form in one pass: upsert filled answers,
    delete ones the user emptied. Summarizes the outcome and reruns."""
    saved_count = 0
    cleared_count = 0
    errors = []

    for section in sections:
        for question in section.get("questions", []):
            qkey = question["key"]
            qtype = question.get("type", "text")
            widget_key = f"refl_input_{qkey}"
            was_saved = qkey in answers

            if qtype == "rating":
                value = st.session_state.get(widget_key, question.get("min", 1))
                result = save_reflection_answer(qkey, answer_number=int(value))
                if result.get("success"):
                    saved_count += 1
                else:
                    errors.append(f"{question.get('label', qkey)}: {result.get('error', 'error')}")
            else:
                text = (st.session_state.get(widget_key, "") or "").strip()
                if text:
                    result = save_reflection_answer(qkey, answer_text=text)
                    if result.get("success"):
                        saved_count += 1
                    else:
                        errors.append(f"{question.get('label', qkey)}: {result.get('error', 'error')}")
                elif was_saved:
                    # User emptied a previously-saved answer -> clear it.
                    result = delete_reflection_answer(qkey)
                    if result.get("success"):
                        cleared_count += 1
                    else:
                        errors.append(f"{question.get('label', qkey)}: {result.get('error', 'error')}")

    if errors:
        st.toast(f"Some answers couldn't be saved: {errors[0]}", icon="⚠️")
    else:
        summary = f"Reflection saved ({saved_count} answer{'s' if saved_count != 1 else ''}"
        summary += f", {cleared_count} cleared)" if cleared_count else ")"
        st.toast(summary)
    st.rerun()


def _render_reflection_question(question: dict, saved: dict):
    """Render one reflection question with its input and saved state (no
    per-question buttons - the whole form is saved by a single button below)."""
    qkey = question["key"]
    qtype = question.get("type", "text")
    widget_key = f"refl_input_{qkey}"
    has_saved = saved is not None

    label = question.get("label")
    if label:
        st.markdown(f"**{label}**")
    st.markdown(question.get("text", ""))

    if qtype == "rating":
        lo, hi = int(question.get("min", 1)), int(question.get("max", 5))
        default_val = int(saved["answer_number"]) if (has_saved and saved.get("answer_number") is not None) else lo
        st.slider(
            "Your rating", min_value=lo, max_value=hi, value=default_val,
            key=widget_key, label_visibility="collapsed",
        )
    else:
        default_text = saved.get("answer_text") if has_saved else ""
        st.text_area(
            "Your answer", value=default_text or "", key=widget_key,
            label_visibility="collapsed", placeholder="Type your answer…",
        )

    if has_saved:
        st.caption(f"Saved {_format_date(saved.get('updated_at') or saved.get('created_at'))}")

    st.markdown("")
