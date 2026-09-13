"""
Free Notes module - a single, user-authored WYSIWYG note per category,
Notion-style: one box, no explicit save button, edits autosave in the
background after a short pause in typing (debounced), never on the
keystroke itself.

Public entry point:
  - render_free_notes(category, key_prefix): one always-visible editor for
    the category's note. It starts blank; the moment it holds real content
    a debounced autosave kicks in, and every further edit keeps autosaving
    the same way - same box throughout, it never resets or gets swapped out
    from under the user while typing. Used by the "Free Question" tab
    (components/cue_questions.py) and the "Free Notes" tab
    (components/key_points.py) - same component, different category, so the
    autosave/clear logic isn't duplicated between the two pages.

Backed by /api/free-notes/* (its own user_free_notes table, see
utils/free_notes_api.py) - pure user-authored rich text with no source to
reference, independent of bookmarks (components/notes.py) and the configured
reflection questions (components/reflection_learning.py). The backend can
technically hold several free notes per category, but this UI only ever
reads/writes the single most recently updated one - "one note per category"
is a UI decision, not a schema constraint.

Autosave mechanics (why a debounce, and why a background thread):
streamlit_quill reports its content back to Python on every single
keystroke, and each of those is a full Streamlit rerun. Calling the save
API synchronously on every one of those reruns (the first version of this
autosave) made the network round-trip part of every keystroke, which is
both wasteful and felt "too fast"/twitchy to type against. Instead:

  - Every keystroke just records the latest content locally (in a plain
    Python object living in st.session_state, not a Streamlit call) and
    (re)starts a countdown (threading.Timer). Typing more resets the
    countdown, so nothing is sent while the user is actively typing.
  - Only once typing pauses for _DEBOUNCE_SECONDS does the countdown fire,
    and it does so on a background thread - so the save happens for real,
    off the request/response cycle, even if the user never triggers another
    rerun (e.g. they stop typing and switch tabs). This is what "always
    saves in the background" means here: persistence doesn't depend on the
    user doing anything else.
  - The background thread never touches st.session_state or any st.*
    call (both require the main script thread's context) - it only mutates
    plain attributes on the shared state object, guarded by a lock. The
    next rerun (any widget interaction anywhere on the page) picks up
    whatever that object says.
  - The editor keeps ONE stable widget key for its entire life - from
    empty, to freshly created, to repeatedly updated - so Streamlit never
    remounts it while the user is typing (a changing key is what causes a
    custom component to lose focus/rebuild, which previously showed up as
    "a new box for every bit of text entered"). The one deliberate,
    intentional remount is the Clear button.
  - render_free_notes is an @st.fragment. Every keystroke still triggers a
    rerun (that's inherent to how the component reports its value back -
    debouncing only delays the network call, not that rerun), but without
    fragment scoping that rerun re-executes and redraws the *entire page*
    on every character, which reads as constant flicker even though the
    editor itself keeps focus. Scoping it to a fragment confines that
    rerun to just this box, so the rest of the page (tabs, sidebar, other
    content) stays untouched while typing.
"""

import threading
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
# note apart from one with real text before autosaving it.
_EMPTY_QUILL_HTML = {"", "<p></p>", "<p><br></p>"}

# How long the user has to stop typing before an edit is actually sent to
# the backend. Long enough that a normal typing burst never triggers a
# save mid-word, short enough that "I stopped typing" still feels instant.
_DEBOUNCE_SECONDS = 2


def _format_date(iso_date: str) -> str:
    if not iso_date:
        return "-"
    try:
        return datetime.fromisoformat(iso_date).strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return iso_date


def _is_blank(html: str) -> bool:
    return (html or "").strip() in _EMPTY_QUILL_HTML


class _NoteAutosaveState:
    """Plain (non-Streamlit) mutable state for one note's debounced
    autosave, shared between the main script thread and the background
    timer thread that performs the actual save. Lives in st.session_state
    (one instance per key_prefix) so it survives reruns, but nothing in
    here calls into Streamlit - that's what makes it safe to touch from a
    background thread."""

    def __init__(self):
        self.loaded = False          # has the initial fetch from the backend happened yet?
        self.note_id = None
        self.saved_content = ""      # last content confirmed persisted
        self.pending_content = None  # latest edit not yet (or not fully) flushed
        self.status = "idle"         # idle | pending | saving | saved | error
        self.error = None
        self.updated_at = None
        self.timer = None
        self.reset_version = 0       # bumped only by the explicit Clear action
        self.lock = threading.Lock()


def _get_state(key_prefix: str, category: str) -> _NoteAutosaveState:
    state_key = f"{key_prefix}_autosave_state"
    state = st.session_state.get(state_key)
    if state is None:
        state = _NoteAutosaveState()
        st.session_state[state_key] = state

    if not state.loaded:
        result = list_free_notes(category)
        if result.get("success"):
            notes = result.get("notes", [])
            existing = notes[0] if notes else None  # most recently updated, if any
            if existing:
                state.note_id = existing["id"]
                state.saved_content = existing.get("content_html", "")
                state.updated_at = existing.get("updated_at")
            state.loaded = True
        else:
            st.error(f"Failed to load note: {result.get('error', 'Unknown error')}")
    return state


def _flush_save(state: _NoteAutosaveState, category: str, user_id: str):
    """Runs on a background thread after the debounce window elapses.
    Persists whatever the latest pending content is - not necessarily what
    it was when the timer was scheduled, in case more edits landed while
    a previous save was still in flight."""
    with state.lock:
        content = state.pending_content
        if content is None:
            return
        state.status = "saving"

    if state.note_id:
        result = update_free_note(state.note_id, content, user_id=user_id)
    else:
        result = create_free_note(category, content, user_id=user_id)

    with state.lock:
        if result.get("success"):
            if not state.note_id:
                state.note_id = result.get("note_id")
            state.saved_content = content
            state.updated_at = datetime.now().isoformat()
            # Only clear the pending marker if nothing newer arrived while
            # this save was in flight - otherwise leave it so the next
            # timer tick (already scheduled by that newer edit) still fires.
            if state.pending_content == content:
                state.pending_content = None
                state.status = "saved"
            state.error = None
        else:
            state.status = "error"
            state.error = result.get("error", "error")
            # Self-heal: retry the same pending content after another
            # debounce window, rather than leaving it stuck silently.
            retry_timer = threading.Timer(_DEBOUNCE_SECONDS, _flush_save, args=(state, category, user_id))
            retry_timer.daemon = True
            state.timer = retry_timer
            retry_timer.start()


def _queue_save(state: _NoteAutosaveState, category: str, user_id: str, content: str):
    """Records the latest edit and (re)starts the debounce countdown."""
    with state.lock:
        state.pending_content = content
        state.status = "pending"
        if state.timer is not None:
            state.timer.cancel()
        timer = threading.Timer(_DEBOUNCE_SECONDS, _flush_save, args=(state, category, user_id))
        timer.daemon = True
        state.timer = timer
        timer.start()


@st.fragment
def render_free_notes(category: str, key_prefix: str):
    """Render the single, debounced-autosave free-note editor for this
    category. Wrapped in @st.fragment so typing only reruns this box, not
    the whole page - see the module docstring."""
    user_id = st.session_state.get("userId")
    if not user_id:
        st.error("User not authenticated")
        return

    state = _get_state(key_prefix, category)

    with st.container(border=True):
        if state.status == "saving":
            st.caption("● Saving…")
        elif state.status == "pending":
            st.caption("● Unsaved changes — saving shortly…")
        elif state.status == "error":
            st.caption(f"⚠️ Could not save: {state.error}")
        elif state.note_id:
            st.caption(f"✓ Saved · last update {_format_date(state.updated_at)}")
        else:
            st.caption("Start typing — it saves automatically a moment after you pause.")

        content = st_quill(
            value=state.saved_content, html=True, toolbar=_BASIC_TOOLBAR,
            placeholder="Write a note…", key=f"{key_prefix}_quill_{state.reset_version}",
        )

        # Only queue a save if this is genuinely new content - not the
        # baseline value being echoed back, and not what's already queued.
        already_known = state.pending_content if state.pending_content is not None else state.saved_content
        if content is not None and content != already_known and not _is_blank(content):
            _queue_save(state, category, user_id, content)

        if state.note_id and not _is_blank(state.saved_content):
            if st.button("🗑️ Clear note", key=f"{key_prefix}_clear"):
                with state.lock:
                    if state.timer is not None:
                        state.timer.cancel()
                        state.timer = None
                    state.pending_content = None
                result = delete_free_note(state.note_id)
                if result.get("success"):
                    state.note_id = None
                    state.saved_content = ""
                    state.updated_at = None
                    state.status = "idle"
                    state.reset_version += 1  # deliberate reset -> fresh blank editor
                    st.toast("Note cleared")
                    st.rerun(scope="fragment")
                else:
                    st.toast(f"Could not clear: {result.get('error', 'error')}", icon="⚠️")
