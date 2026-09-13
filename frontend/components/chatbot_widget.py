"""
Learning Assistant floating widget - the chatbot's new home, replacing the
old "Learning with Chatbot Assistance" menu page (components/chatbot.py,
pages/chatbot.py - both removed). A proactive nudge only means anything if
the learner can actually see it without navigating to a specific menu
first, so this renders as a small bubble pinned to a corner of every page
(see the single render_chatbot_widget() call in pages/learner_profile.py,
placed outside the per-page branching so it's on-screen everywhere) rather
than being one more page you have to open.

Public entry point:
  - render_chatbot_widget(): a collapsed bubble (💬, pulses if there's an
    unread message) that expands into a compact chat panel on click -
    same conversation state/backend as the old page (session-only history,
    /api/chatbot/* -> local Qwen via Ollama), plus a one-shot proactive
    greeting: if the learner has any Remedial units, the assistant opens
    the conversation itself instead of waiting to be asked, and the bubble
    shows unread until they open the panel.

Deliberately independent from the rest of the app otherwise: it does NOT
read or write the database, Neo4j, or any adaptive-learning state beyond
that one Remedial-unit count used for the proactive nudge - conversation
history lives purely in Streamlit session state, same as before.
"""

import hashlib
import uuid

import streamlit as st

from utils.chatbot_api import send_chat_message
from utils.practice_api import record_chatbot_attempt, get_learning_path_stats
from utils.notes_api import get_saved_source_ids, SOURCE_CHAT
from components.notes import render_save_button

_HISTORY_KEY = "chatbot_messages"
_CONV_KEY = "chatbot_conversation_id"
_OPEN_KEY = "chatbot_widget_open"
_UNREAD_KEY = "chatbot_widget_unread"
_PROACTIVE_SENT_KEY = "chatbot_proactive_sent"
_SAVED_IDS_CACHE_KEY = "chatbot_saved_ids_cache"
_SAVED_IDS_DIRTY_KEY = "chatbot_saved_ids_dirty"

_WELCOME = (
    "👋 Hi! I'm your learning assistant. Ask me anything about your study "
    "material - programming concepts, examples, or anything you're stuck on."
)


def _chat_source_id(content: str) -> str:
    """Stable id for a chat message note - a content hash, so saving the same
    message content twice is a no-op (dedupe) rather than a duplicate."""
    return "msg_" + hashlib.md5((content or "").encode("utf-8")).hexdigest()[:16]


def _init_state():
    if _HISTORY_KEY not in st.session_state:
        st.session_state[_HISTORY_KEY] = []
    if _CONV_KEY not in st.session_state:
        st.session_state[_CONV_KEY] = str(uuid.uuid4())
    st.session_state.setdefault(_OPEN_KEY, False)
    st.session_state.setdefault(_UNREAD_KEY, False)


def _maybe_send_proactive_nudge():
    """
    Once per session: if the learner has any Remedial units, have the
    assistant open the conversation itself instead of waiting to be asked
    (validated by Khan Academy's Khanmigo redesign - a purely reactive
    tutor goes largely unused). Marks the bubble unread so it's noticeable
    from any page, not just if/when they happen to open the panel.
    """
    if st.session_state.get(_PROACTIVE_SENT_KEY):
        return
    # Set the guard before the (possibly failing) network call so a slow/
    # down backend can't cause this to retry on every single rerun.
    st.session_state[_PROACTIVE_SENT_KEY] = True

    stats = get_learning_path_stats()
    if not stats.get("success"):
        return
    remedial = stats.get("remedial_units", 0)
    if remedial <= 0:
        return

    message = (
        f"👋 Hi again! I noticed you still have **{remedial} unit{'s' if remedial != 1 else ''}** "
        "marked Remedial. Want to go over what's tripping you up? Just ask me about any concept "
        "you're stuck on."
    )
    st.session_state[_HISTORY_KEY].append({"role": "assistant", "content": message})
    st.session_state[_UNREAD_KEY] = True


def render_chatbot_widget():
    """Render the floating bubble, expanding into the chat panel when open."""
    if not st.session_state.get("logged_in"):
        return  # only ever called post-login anyway (see pages/learner_profile.py); safe no-op otherwise

    _init_state()
    _maybe_send_proactive_nudge()

    is_open = st.session_state[_OPEN_KEY]
    is_unread = st.session_state[_UNREAD_KEY]

    bubble_state = "unread" if (is_unread and not is_open) else "idle"
    with st.container(key=f"chatbot_bubble_wrap_{bubble_state}"):
        if st.button("✕" if is_open else "💬", key="chatbot_bubble_btn", help="Learning Assistant"):
            opening = not is_open
            st.session_state[_OPEN_KEY] = opening
            if opening:
                st.session_state[_UNREAD_KEY] = False  # opening it counts as "seen"
                st.session_state[_SAVED_IDS_DIRTY_KEY] = True  # refetch once, fresh, for this open
            st.rerun()

    if is_open:
        _render_panel()


def _get_saved_chat_ids() -> set:
    """
    Cached across reruns instead of re-fetched on every single one. While
    the panel is open, it re-renders on EVERY app-wide interaction (normal
    Streamlit behavior - any click anywhere reruns the whole script), so
    hitting the backend for this on every single one of those - even
    clicks that have nothing to do with chat - was needless latency
    (this was the actual cause behind "minimize feels slower now").

    Refetched fresh only when the panel is (re)opened - not after every
    save/remove click inside it (that would need render_save_button,
    shared with other pages, to report back whether it just toggled
    something, which it doesn't), so a message's save icon can very
    briefly show its old state immediately after being clicked,
    correcting itself next time the panel is reopened. A fine trade for
    not re-fetching on every click across the whole app. A brand-new
    message's own icon is never affected by this - it can't already be in
    a stale "saved" set that predates its own existence.
    """
    if st.session_state.get(_SAVED_IDS_DIRTY_KEY, True):
        st.session_state[_SAVED_IDS_CACHE_KEY] = get_saved_source_ids(SOURCE_CHAT)
        st.session_state[_SAVED_IDS_DIRTY_KEY] = False
    return st.session_state[_SAVED_IDS_CACHE_KEY]


def _render_panel():
    with st.container(key="chatbot_panel"):
        title_col, minimize_col = st.columns([5, 1])
        with title_col:
            st.markdown("**💬 Learning Assistant**")
        with minimize_col:
            if st.button("➖", key="chatbot_minimize_btn", help="Minimize", use_container_width=True):
                st.session_state[_OPEN_KEY] = False
                st.rerun()
        st.caption("Standalone AI tutor on a local model - doesn't see your Test/Practice data.")

        history = st.session_state[_HISTORY_KEY]
        saved_chat_ids = _get_saved_chat_ids()

        messages = st.container(height=320)
        with messages:
            if not history:
                with st.chat_message("assistant"):
                    st.markdown(_WELCOME)
            else:
                for idx, msg in enumerate(history):
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])
                        if msg["role"] == "assistant" and msg.get("content"):
                            _render_note_icon(msg["content"], saved_chat_ids, idx)

        # A form (not st.chat_input, which docks itself to the bottom of the
        # WHOLE app natively - that would fight this panel's own fixed
        # positioning) so Enter submits like a normal chat box.
        with st.form("chatbot_widget_form", clear_on_submit=True, border=False):
            input_col, send_col = st.columns([4, 1])
            with input_col:
                prompt = st.text_input(
                    "Message", label_visibility="collapsed", placeholder="Type your question…",
                )
            with send_col:
                submitted = st.form_submit_button("➤", use_container_width=True)

        if submitted and prompt.strip():
            prompt = prompt.strip()
            history.append({"role": "user", "content": prompt})
            # Fire-and-forget: count this prompt for Learning Path stats -
            # pure analytics, doesn't feed the assistant any user/mastery data.
            record_chatbot_attempt()

            with messages:
                with st.chat_message("user"):
                    st.markdown(prompt)
                with st.chat_message("assistant"):
                    with st.spinner("Thinking…"):
                        result = send_chat_message(history)
                    if result.get("success"):
                        reply = result.get("reply", "")
                        st.markdown(reply)
                        if reply:
                            history.append({"role": "assistant", "content": reply})
                    else:
                        error = result.get("error") or "The assistant is unavailable right now. Please try again."
                        st.error(f"⚠️ {error}")
            st.rerun()

        clear_col, _spacer = st.columns([1, 2])
        with clear_col:
            if st.button("🗑️ Clear", key="chatbot_widget_clear", use_container_width=True):
                st.session_state[_HISTORY_KEY] = []
                st.session_state[_CONV_KEY] = str(uuid.uuid4())
                st.rerun()


def _render_note_icon(content: str, saved_chat_ids: set, index: int):
    """Icon-only Save-to-Notes toggle (🔖/✅) - the full-text version
    (components/notes.py's default) doesn't fit this panel's width."""
    conversation_id = st.session_state.get(_CONV_KEY)
    render_save_button(
        SOURCE_CHAT, _chat_source_id(content), content,
        title="Chatbot answer",
        source_ref={"conversation_id": conversation_id, "role": "assistant", "index": index},
        saved_ids=saved_chat_ids, key=f"chatwidget_note_{index}",
        use_container_width=False, icon_only=True,
    )
