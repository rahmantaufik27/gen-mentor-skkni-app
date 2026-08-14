"""
Learning with Chatbot Assistance learning method.

Self-contained module: exposes render_chatbot() as its only public entry
point. A standalone AI tutor chat - conversation history lives purely in
Streamlit session state (this component's own key), and every turn is sent
to the backend's /api/chatbot/* endpoints (utils/chatbot_api.py), which
forward it to a pluggable local LLM (Ollama / qwen2.5:1.5b by default -
see backend/services/llm/).

Deliberately independent from the rest of the app: it does NOT read or write
the database, Neo4j, the user model, recommendations, or any adaptive-learning
state - it only manages its own chat history in session state.
"""

import hashlib
import uuid

import streamlit as st

from utils.chatbot_api import send_chat_message
from utils.practice_api import record_chatbot_attempt
from utils.notes_api import get_saved_source_ids, SOURCE_CHAT
from components.notes import render_save_button

# Session-state key that holds this chat's history. Prefixed to avoid
# colliding with any other component's state.
_HISTORY_KEY = "chatbot_messages"
# A per-conversation id, kept in the note's source_ref so a saved message can be
# traced back to the discussion it came from (reset when the chat is cleared).
_CONV_KEY = "chatbot_conversation_id"


def _chat_source_id(content: str) -> str:
    """Stable id for a chat message note - a content hash, so saving the same
    message content twice is a no-op (dedupe) rather than a duplicate."""
    return "msg_" + hashlib.md5((content or "").encode("utf-8")).hexdigest()[:16]

_WELCOME = (
    "👋 Hi! I'm your learning assistant. Ask me anything about your study "
    "material - programming concepts, examples, or anything you're stuck on."
)


def _init_state():
    if _HISTORY_KEY not in st.session_state:
        st.session_state[_HISTORY_KEY] = []
    if _CONV_KEY not in st.session_state:
        st.session_state[_CONV_KEY] = str(uuid.uuid4())


def _render_assistant_note_button(content: str, saved_chat_ids: set, index):
    """Save-to-Notes toggle for one assistant message, snapshotting its text."""
    conversation_id = st.session_state.get(_CONV_KEY)
    _, note_col = st.columns([4, 1])
    with note_col:
        render_save_button(
            SOURCE_CHAT, _chat_source_id(content), content,
            title="Chatbot answer",
            source_ref={"conversation_id": conversation_id, "role": "assistant", "index": index},
            saved_ids=saved_chat_ids, key=f"note_chat_{index}",
        )


def render_chatbot():
    """Render the Learning with Chatbot Assistance chat interface."""
    _init_state()
    history = st.session_state[_HISTORY_KEY]
    # Which assistant messages are already saved to Notes - fetched once so each
    # message's toggle renders in the right state.
    saved_chat_ids = get_saved_source_ids(SOURCE_CHAT)

    # --- Header + reset ---------------------------------------------------
    header_col, action_col = st.columns([4, 1])
    with header_col:
        st.markdown("#### 💬 Learning with Chatbot Assistance")
        st.caption("A standalone AI tutor running on a local model. It doesn't see your Test, Practice, or mastery data.")
    with action_col:
        # Always enabled - clicking with an empty history is a harmless no-op.
        # (A `disabled=not history` guard would lag one render after the first
        # message, since this button renders before the input is processed.)
        if st.button("🗑️ Clear chat", use_container_width=True):
            st.session_state[_HISTORY_KEY] = []
            st.session_state[_CONV_KEY] = str(uuid.uuid4())
            st.rerun()

    # --- Conversation window ---------------------------------------------
    # A fixed-height, scrollable container holds the whole conversation, so it
    # reads like a standard chat: messages flow top (oldest) to bottom
    # (newest), the window scrolls, and the input stays just below it. New
    # turns are written into this same container so they appear at the bottom.
    conversation = st.container(height=460)
    with conversation:
        if not history:
            with st.chat_message("assistant"):
                st.markdown(_WELCOME)
        else:
            for idx, msg in enumerate(history):
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                    # Offer Save-to-Notes on assistant answers (the useful bits).
                    if msg["role"] == "assistant" and msg.get("content"):
                        _render_assistant_note_button(msg["content"], saved_chat_ids, idx)

    # --- Input (kept at the bottom, below the conversation) --------------
    prompt = st.chat_input("Type your question…")

    # --- Reply ------------------------------------------------------------
    if prompt:
        prompt = prompt.strip()
        if not prompt:
            return

        history.append({"role": "user", "content": prompt})
        # Fire-and-forget: count this prompt for Learning Path stats. This is a
        # pure analytics ping - it does NOT feed the chatbot any user/mastery
        # data, so the assistant stays a standalone, independent module.
        record_chatbot_attempt()
        # Write the new turn into the conversation window so it lands at the
        # bottom (newest visible) and the window scrolls to it.
        with conversation:
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                with st.spinner("Thinking…"):
                    result = send_chat_message(history)

                if result.get("success"):
                    reply = result.get("reply", "")
                    st.markdown(reply)
                    history.append({"role": "assistant", "content": reply})
                    # Let the learner save this answer right away (it's brand new,
                    # so it won't be in saved_chat_ids yet -> shows "Save to Notes").
                    if reply:
                        _render_assistant_note_button(reply, saved_chat_ids, len(history) - 1)
                else:
                    # Keep the user's message in history so they can see what they
                    # asked, but don't record a bogus assistant turn - they can
                    # simply ask again once the issue (e.g. Ollama not running) is
                    # resolved.
                    error = result.get("error") or "The assistant is unavailable right now. Please try again."
                    st.error(f"⚠️ {error}")
