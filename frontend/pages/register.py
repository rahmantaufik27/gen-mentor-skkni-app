"""User Registration Page

Same split layout as pages/login.py (navy brand panel left, form right);
the shared pieces live in utils/auth_layout.py. On success the user is sent
to the Login page, which shows the backend's message (e.g. "check your
email to confirm your address").
"""

from html import escape

import httpx
import streamlit as st

import config
from utils.auth_layout import alert, brand_panel, form_bottom, form_top, heading, hide_app_chrome
from utils.theme import inject_theme

if "registration_error" not in st.session_state:
    st.session_state.registration_error = None

st.set_page_config(page_title="GAMASKILL - Create account", page_icon="🎓", layout="wide", initial_sidebar_state="collapsed")

hide_app_chrome()
inject_theme()


def register_user(full_name: str, email: str, password: str, confirm_password: str):
    """Register a new user with the backend. Returns (ok, message)."""
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{config.backend_endpoint}api/auth/register",
                json={"full_name": full_name, "email": email,
                      "password": password, "confirm_password": confirm_password},
            )
        result = response.json()
        if response.status_code == 201:
            return True, result.get("message", "Account created. Please sign in.")
        return False, result.get("error", "Registration failed")
    except httpx.ConnectError:
        return False, "Cannot connect to backend server. Make sure it's running on localhost:5000"
    except Exception as e:
        return False, f"Error: {str(e)}"


brand_col, form_col = st.columns([1.05, 1], gap="small")

with brand_col:
    brand_panel("Find your level on every unit. <em>Then close the gap.</em>",
                "Create a free account to see where you stand on each SKKNI unit and get a personalized "
                "path of materials and practice questions.")

with form_col:
    with st.container(key="gm_login_form"):
        form_top()
        heading("Create your account", "It takes a minute. You'll use this email to sign in.")

        # registration_error holds ready-made (escaped) HTML.
        if st.session_state.registration_error:
            alert("error", st.session_state.registration_error)
            st.session_state.registration_error = None

        with st.form("registration_form", border=False):
            full_name = st.text_input("Full name", placeholder="John Doe", key="full_name_register")
            email = st.text_input("Email", placeholder="john@example.com", key="email_register")
            password = st.text_input("Password", type="password", placeholder="At least 8 characters",
                                     key="password_register")
            confirm_password = st.text_input("Confirm password", type="password",
                                             placeholder="Re-enter your password", key="confirm_password_register")
            st.markdown('<div class="gm-login-hint">At least 8 characters. A mix of upper- and lowercase '
                        'letters and numbers is stronger.</div>', unsafe_allow_html=True)
            submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)

        if submitted:
            errors = []
            if not full_name.strip():
                errors.append("Enter your full name.")
            if not email.strip():
                errors.append("Enter your email address.")
            elif "@" not in email or "." not in email:
                errors.append("Enter a valid email address.")
            if not password:
                errors.append("Choose a password.")
            elif len(password) < 8:
                errors.append("Password must be at least 8 characters.")
            if password and password != confirm_password:
                errors.append("The two passwords do not match.")

            if errors:
                if len(errors) == 1:
                    st.session_state.registration_error = f"<b>{escape(errors[0])}</b>"
                else:
                    items = "".join(f"<li>{escape(e)}</li>" for e in errors)
                    st.session_state.registration_error = (
                        f'<b>Please fix the following:</b><ul class="gm-login-errlist">{items}</ul>')
                st.rerun()
            else:
                with st.spinner("Creating your account..."):
                    success, message = register_user(full_name.strip(), email.strip(), password, confirm_password)
                if success:
                    # Shown as a green alert on the Login page.
                    st.session_state.registration_just_completed = True
                    st.session_state.registration_message = message
                    st.switch_page("pages/login.py")
                else:
                    st.session_state.registration_error = f"<b>{escape(message)}</b>"
                    st.rerun()

        st.markdown('<div class="gm-login-divider">Already have an account?</div>', unsafe_allow_html=True)
        if st.button("Sign in", key="gm_register_signin", use_container_width=True):
            st.switch_page("pages/login.py")

        form_bottom()
