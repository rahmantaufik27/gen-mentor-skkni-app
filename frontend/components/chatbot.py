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

import streamlit as st

from utils.chatbot_api import send_chat_message
from utils.practice_api import record_chatbot_attempt

# Session-state key that holds this chat's history. Prefixed to avoid
# colliding with any other component's state.
_HISTORY_KEY = "chatbot_messages"

_WELCOME = (
    "👋 Hi! I'm your learning assistant. Ask me anything about your study "
    "material - programming concepts, examples, or anything you're stuck on."
)


def _init_state():
    if _HISTORY_KEY not in st.session_state:
        st.session_state[_HISTORY_KEY] = []


def render_chatbot():
    """Render the Learning with Chatbot Assistance chat interface."""
    _init_state()
    history = st.session_state[_HISTORY_KEY]

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
            st.rerun()

    # st.divider()
    prompt = st.chat_input("Type your question…")

    # --- Conversation history --------------------------------------------
    if not history:
        with st.chat_message("assistant"):
            st.markdown(_WELCOME)
    else:
        for msg in history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # --- Input + reply ----------------------------------------------------
    if prompt:
        prompt = prompt.strip()
        if not prompt:
            return

        history.append({"role": "user", "content": prompt})
        # Fire-and-forget: count this prompt for Learning Path stats. This is a
        # pure analytics ping - it does NOT feed the chatbot any user/mastery
        # data, so the assistant stays a standalone, independent module.
        record_chatbot_attempt()
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                result = send_chat_message(history)

            if result.get("success"):
                reply = result.get("reply", "")
                st.markdown(reply)
                history.append({"role": "assistant", "content": reply})
            else:
                # Keep the user's message in history so they can see what they
                # asked, but don't record a bogus assistant turn - they can
                # simply ask again once the issue (e.g. Ollama not running) is
                # resolved.
                error = result.get("error") or "The assistant is unavailable right now. Please try again."
                st.error(f"⚠️ {error}")
