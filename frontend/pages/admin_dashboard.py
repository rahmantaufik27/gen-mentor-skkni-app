"""
Admin Dashboard - entry point for the admin module.

Deliberately separate from main.py/learner_profile.py (the learner
interface): its own st.set_page_config(), its own auth guard
(admin_logged_in, not the learner's logged_in), and its own sidebar/section
registry (components/admin_shell.py) instead of the learner's NAV_ITEMS.

To add a new admin feature later: build its own render_* component (see
components/admin_users.py for the pattern) and add one entry to
ADMIN_SECTIONS below - nothing else here needs to change.
"""

import streamlit as st
from utils.theme import inject_theme
from components.admin_shell import require_admin_authentication, render_admin_sidebar, render_admin_header
from components.admin_users import render_admin_users

st.set_page_config(page_title="Admin Dashboard - Gen-Mentor", page_icon="🛠️", layout="wide", initial_sidebar_state="expanded")
st.set_option("client.showSidebarNavigation", False)

inject_theme()

require_admin_authentication()

# Admin section registry - add future admin features here, e.g.:
# "materials": {"label": "📚 Materials", "render": render_admin_materials},
ADMIN_SECTIONS = {
    "users": {"label": "👥 User Management", "render": render_admin_users},
}

if st.session_state.get("admin_section") not in ADMIN_SECTIONS:
    st.session_state.admin_section = "users"

render_admin_sidebar(active=st.session_state.admin_section, sections=ADMIN_SECTIONS)

active_section = ADMIN_SECTIONS[st.session_state.admin_section]

if render_admin_header(active_section["label"]):
    st.session_state.admin_logged_in = False
    st.session_state.admin_email = None
    st.switch_page("pages/admin_login.py")

active_section["render"]()
