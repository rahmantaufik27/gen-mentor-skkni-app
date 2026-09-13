"""
My Profile page - the post-login landing page (see pages/learner_profile.py).

Public entry point:
  - render_profile_landing(): two tabs -
      - "🏠 Overview": a greeting, the proactive nudge banner (moved here
        from Data Analytics - see components/mastery_dashboard.py::
        render_nudge_banner - since this tab is the actual first thing a
        user sees on login now), and quick links to the other top-level
        pages.
      - "⚙️ Update Profile": render_user_profile() - identity (name,
        read-only email, member-since), profile photo upload/preview, and
        change password. This used to be the entire My Profile page by
        itself; it's now one tab alongside Overview.

Backed by /api/auth/profile*, /api/auth/change-password (see
utils/profile_api.py and backend/controllers/auth_controller.py) - email is
deliberately not editable here (it's the login identifier; changing it
safely needs its own re-verification flow, out of scope for this form).
"""

from datetime import datetime

import streamlit as st

from utils.profile_api import get_profile, update_profile, change_password, upload_profile_photo, profile_photo_url
from utils.theme import avatar_initials
from components.mastery_dashboard import render_nudge_banner

# Shown collapsed on the Overview tab, mainly for a first-time/returning
# learner who wants a refresher on what the platform actually does -
# doesn't compete with the actionable nudge banner or quick links below it.
ABOUT_TEXT = (
    "GAMASKILL (\"Gateway for Adaptive Mastery and Advancement of Skills\") is an adaptive, "
    "competency based learning platform aligned with Indonesia's SKKNI national work "
    "competency standard for programming. The flow begins with a Placement Test (Pre-Test) "
    "that assesses a learner's mastery across six programming competency units using an "
    "inference engine (Dynamic Bayesian Network or manual) built on Bloom's taxonomy levels "
    "(C1 to C6). It then automatically classifies each unit as \"Mastered\" or \"Remedial\" and "
    "recommends a personalized learning path: reading materials sourced from a Neo4j "
    "knowledge graph, question and answer sessions with an AI tutor chatbot (a local Qwen LLM "
    "served through Ollama), and generative practice questions, culminating in a Post-Test "
    "that confirms the learner's progress. Beyond this adaptive learning core, the app also "
    "includes supporting features such as personal notes and learning reflections, a peer "
    "discussion forum per unit (with best answer marking), and engagement tracking (streaks, "
    "badges, and anonymous peer benchmarking)."
)


def _format_date(iso_date: str) -> str:
    if not iso_date:
        return "-"
    try:
        return datetime.fromisoformat(iso_date).strftime("%d-%m-%Y")
    except ValueError:
        return iso_date


def render_profile_landing():
    """Render My Profile: the Overview + Update Profile tabs."""
    tab_overview, tab_update = st.tabs(["🏠 Overview", "⚙️ Update Profile"])
    with tab_overview:
        _render_overview_tab()
    with tab_update:
        render_user_profile()


def _render_overview_tab():
    """Greeting + nudge banner + quick links to the other top-level pages -
    the actual first thing a user sees after logging in."""
    name = st.session_state.get("user_name") or "there"
    st.markdown(f"#### 👋 Welcome back, {name.split()[0] if name != 'there' else name}!")
    st.caption("Here's a quick look at where you left off.")

    with st.expander("ℹ️ About GAMASKILL"):
        st.markdown(ABOUT_TEXT)

    render_nudge_banner()

    st.markdown("")
    st.markdown("###### Quick Links")
    links = [
        ("📊 Data Analytics", "data_analytics"),
        ("📈 Engagement", "engagement"),
        ("📚 Learning Path", "learning_path"),
        ("📝 Test", "test"),
    ]
    for col, (label, page_key) in zip(st.columns(len(links)), links):
        with col:
            if st.button(label, key=f"overview_link_{page_key}", use_container_width=True):
                st.session_state.current_page = page_key
                st.rerun()


def render_user_profile():
    """Render the "Update Profile" tab: identity, photo, and password sections."""
    result = get_profile()
    if not result.get("success"):
        st.error(f"Failed to load your profile: {result.get('error', 'Unknown error')}")
        return
    user = result.get("user", {})

    with st.container(border=True):
        _render_identity_section(user)

    st.markdown("")
    with st.container(border=True):
        _render_photo_section(user)

    st.markdown("")
    with st.container(border=True):
        _render_password_section()


def _render_identity_section(user: dict):
    st.markdown("#### 👤 Profile")
    st.caption("Your general account information.")

    with st.form("profile_identity_form"):
        full_name = st.text_input("Full Name", value=user.get("full_name", ""))
        st.text_input("Email", value=user.get("email", ""), disabled=True, help="Email can't be changed here.")
        st.caption(f"Member since {_format_date(user.get('created_at'))}")

        if st.form_submit_button("Save Changes", type="primary"):
            if not full_name.strip():
                st.toast("Full name can't be empty", icon="⚠️")
            else:
                res = update_profile(full_name.strip())
                if res.get("success"):
                    # Keep the header user-chip (reads session_state.user_name
                    # directly) in sync for the rest of this session.
                    st.session_state.user_name = full_name.strip()
                    st.toast("Profile updated")
                    st.rerun()
                else:
                    st.toast(f"Could not update profile: {res.get('error', 'error')}", icon="⚠️")


def _render_photo_section(user: dict):
    st.markdown("#### 🖼️ Profile Photo")

    preview_col, upload_col = st.columns([1, 3])
    with preview_col:
        if user.get("profile_photo_path"):
            st.image(profile_photo_url(user["id"]), width=100)
        else:
            st.markdown(
                f"<div class='gm-avatar' style='width:100px; height:100px; font-size:32px;'>"
                f"{avatar_initials(user.get('full_name'))}</div>",
                unsafe_allow_html=True,
            )
    with upload_col:
        uploaded = st.file_uploader(
            "Upload a new photo", type=["png", "jpg", "jpeg"], key="profile_photo_uploader",
            help="PNG or JPG.",
        )
        if uploaded is not None:
            if st.button("Save Photo", type="primary", key="profile_photo_save_btn"):
                res = upload_profile_photo(uploaded.getvalue(), uploaded.name, uploaded.type or "image/jpeg")
                if res.get("success"):
                    # Keep the header avatar (reads session_state.user_photo
                    # directly) in sync for the rest of this session.
                    st.session_state.user_photo = res.get("filename")
                    st.toast("Photo updated")
                    st.rerun()
                else:
                    st.toast(f"Could not upload photo: {res.get('error', 'error')}", icon="⚠️")


def _render_password_section():
    st.markdown("#### 🔒 Change Password")

    with st.form("profile_password_form", clear_on_submit=True):
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password", help="At least 8 characters.")
        confirm_password = st.text_input("Confirm New Password", type="password")

        if st.form_submit_button("Update Password", type="primary"):
            if not current_password or not new_password:
                st.toast("Fill in all password fields", icon="⚠️")
            elif len(new_password) < 8:
                st.toast("New password must be at least 8 characters", icon="⚠️")
            elif new_password != confirm_password:
                st.toast("New password and confirmation don't match", icon="⚠️")
            else:
                res = change_password(current_password, new_password)
                if res.get("success"):
                    st.toast("Password changed")
                else:
                    st.toast(f"Could not change password: {res.get('error', 'error')}", icon="⚠️")
