"""
Admin Login Page

Separate from the learner login (pages/login.py): uses its own backend
endpoint (/api/admin/login) and its own session-state flag
(admin_logged_in), never mixed with the learner's logged_in flag.
"""

import streamlit as st
from utils.theme import inject_theme, render_brand
from utils.admin_api import admin_login

# Initialize session state
if "admin_login_error" not in st.session_state:
    st.session_state.admin_login_error = None

st.set_page_config(page_title="Admin Login - Gen-Mentor", page_icon="🛠️", layout="centered", initial_sidebar_state="collapsed")

# ============================================================================
# HIDE STREAMLIT'S AUTOMATIC PAGE SIDEBAR (auth pages don't use the app shell)
# ============================================================================
st.markdown(
    """
    <style>
        [data-testid="collapsedControl"] { display: none !important; }
        [data-testid="baseButton-header-close"] { display: none !important; }
        ul[data-testid="stSidebarNavigation"] { display: none !important; }
        section[data-testid="stSidebar"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================================
# SHARED THEME (palette, typography, cards, buttons)
# ============================================================================
inject_theme()

render_brand(auth_style=True)

with st.container(border=True):
    st.markdown("<h2 style='text-align: center; margin-top:0;'>Admin Login</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: var(--text-muted);'>Sign in to manage users</p>", unsafe_allow_html=True)

    if st.session_state.admin_login_error:
        st.error(st.session_state.admin_login_error)
        st.session_state.admin_login_error = None

    with st.form("admin_login_form"):
        email = st.text_input(
            "Email",
            placeholder="admin@example.com",
            key="admin_email_login"
        )

        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter admin password",
            key="admin_password_login"
        )

        submitted = st.form_submit_button(
            "Sign In",
            type="primary",
            use_container_width=True
        )

        if submitted:
            errors = []

            if not email.strip():
                errors.append("Email is required")
            if not password:
                errors.append("Password is required")

            if errors:
                for error in errors:
                    st.error(f"• {error}")
            else:
                with st.spinner("Signing in..."):
                    result = admin_login(email.strip(), password)

                if result.get("success"):
                    st.session_state.admin_logged_in = True
                    st.session_state.admin_email = email.strip().lower()
                    st.switch_page("pages/admin_dashboard.py")
                else:
                    st.session_state.admin_login_error = result.get("error", "Admin login failed")
                    st.rerun()

col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("← Back to Learner Login", use_container_width=True):
        st.switch_page("pages/login.py")
