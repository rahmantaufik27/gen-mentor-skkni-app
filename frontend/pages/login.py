"""User Login Page

Split layout (see the "GAMASKILL Sign In" mockup): a navy brand panel on
the left, the form on the right. On a narrow screen the brand panel is
hidden and a small logo sits above the form.

Also the landing page for the two emailed one-time links (see
backend/services/account_email_service.py):
  /login?verify=<token>  confirms a new account's email address
  /login?reset=<token>   opens the "choose a new password" form
and hosts the "Forgot password?" request form.
"""

from html import escape

import httpx
import streamlit as st

import config
from utils.auth_layout import alert as _alert, brand_panel, form_bottom, form_top, heading as _heading, hide_app_chrome
from utils.theme import inject_theme

# Initialize session state
if "login_error" not in st.session_state:
    st.session_state.login_error = None
if "login_notice" not in st.session_state:
    st.session_state.login_notice = None
if "login_mode" not in st.session_state:
    st.session_state.login_mode = "login"  # "login" | "forgot" | "sent"
if "unverified_email" not in st.session_state:
    st.session_state.unverified_email = None

st.set_page_config(page_title="GAMASKILL - Sign in", page_icon="🎓", layout="wide", initial_sidebar_state="collapsed")

hide_app_chrome()
inject_theme()


def _auth_post(path: str, payload: dict):
    """POST to /api/auth/<path>. Returns (ok, message, raw_json)."""
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(f"{config.backend_endpoint}api/auth/{path}", json=payload)
        result = response.json()
        if response.status_code == 200:
            return True, result.get("message", "Done"), result
        return False, result.get("error", "Request failed"), result
    except httpx.ConnectError:
        return False, "Cannot connect to backend server. Make sure it's running on localhost:5000", {}
    except Exception as e:
        return False, f"Error: {str(e)}", {}


def login_user(email: str, password: str):
    """Authenticate user with the backend. Returns (ok, message, user, email_not_verified)."""
    ok, message, result = _auth_post("login", {"email": email, "password": password})
    if ok:
        return True, "Login successful", result.get("user", {}), False
    return False, message, None, bool(result.get("email_not_verified"))


# ============================================================================
# EMAILED LINK: confirm email address
# ============================================================================
verify_token = st.query_params.get("verify")
if verify_token:
    ok, message, _ = _auth_post("verify-email", {"token": verify_token})
    st.query_params.clear()
    if ok:
        st.session_state.login_notice = message
        st.session_state.unverified_email = None
    else:
        st.session_state.login_error = message

reset_token = st.query_params.get("reset")

brand_col, form_col = st.columns([1.05, 1], gap="small")

# ============================================================================
# LEFT: brand panel
# ============================================================================
with brand_col:
    brand_panel("Know your level on every unit. <em>Then close the gap.</em>",
                "Pick up where you left off: your levels, recommended materials and practice questions are waiting.")

# ============================================================================
# RIGHT: form
# ============================================================================
with form_col:
    with st.container(key="gm_login_form"):
        form_top()

        if reset_token:
            # ================================================================
            # EMAILED LINK: choose a new password
            # ================================================================
            _heading("Choose a new password", "Enter a new password for your GAMASKILL account.")
            if st.session_state.login_error:
                _alert("error", escape(st.session_state.login_error))
                st.session_state.login_error = None
            with st.form("reset_password_form", border=False):
                new_password = st.text_input("New password", type="password", placeholder="At least 8 characters")
                confirm_new = st.text_input("Confirm new password", type="password", placeholder="Re-enter your new password")
                if st.form_submit_button("Save new password", type="primary", use_container_width=True):
                    if len(new_password) < 8:
                        _alert("error", "Password must be at least 8 characters.")
                    elif new_password != confirm_new:
                        _alert("error", "The two passwords do not match.")
                    else:
                        ok, message, _ = _auth_post("reset-password", {"token": reset_token, "new_password": new_password})
                        st.query_params.clear()
                        if ok:
                            st.session_state.login_notice = message
                        else:
                            st.session_state.login_error = message
                        st.rerun()

        elif st.session_state.login_mode == "forgot":
            # ================================================================
            # FORGOT PASSWORD: request a reset link
            # ================================================================
            _heading("Reset your password",
                     "Enter the email you registered with. We'll send a link to choose a new password. "
                     "It expires in 30 minutes.")
            with st.form("forgot_password_form", border=False):
                forgot_email = st.text_input("Email", placeholder="you@example.com", key="email_forgot")
                if st.form_submit_button("Send reset link", type="primary", use_container_width=True):
                    if "@" not in forgot_email or "." not in forgot_email:
                        _alert("error", "Enter a valid email address.")
                    else:
                        with st.spinner("Sending..."):
                            ok, message, _ = _auth_post("forgot-password", {"email": forgot_email.strip()})
                        if ok:
                            st.session_state.login_mode = "sent"
                            st.rerun()
                        else:
                            _alert("error", escape(message))
            if st.button("← Back to sign in", key="gm_login_back_signin"):
                st.session_state.login_mode = "login"
                st.rerun()

        elif st.session_state.login_mode == "sent":
            # ================================================================
            # RESET LINK SENT
            # ================================================================
            _heading("Check your email", "If that address has an account, a reset link is on its way.")
            _alert("ok", "Open the link from <b>GAMASKILL</b> within 30 minutes. Not there? Check your spam folder.")
            if st.button("Back to sign in", key="gm_login_sent_back", use_container_width=True):
                st.session_state.login_mode = "login"
                st.rerun()

        else:
            # ================================================================
            # SIGN IN
            # ================================================================
            _heading("Welcome back", "Sign in to continue your learning path.")

            # Message carried over from Register (e.g. "check your email")
            if st.session_state.get("registration_just_completed"):
                _alert("ok", escape(st.session_state.get("registration_message") or "Account created. Please sign in."))
                st.session_state.registration_just_completed = False
                st.session_state.registration_message = None
            if st.session_state.login_notice:
                _alert("ok", escape(st.session_state.login_notice))
                st.session_state.login_notice = None

            if st.session_state.unverified_email:
                _alert("warn", "<b>Confirm your email first.</b> We sent a link to "
                       f"{escape(st.session_state.unverified_email)}.")
                if st.button("Send the confirmation email again", key="resend_verification", use_container_width=True):
                    with st.spinner("Sending..."):
                        ok, message, _ = _auth_post("resend-verification", {"email": st.session_state.unverified_email})
                    if ok:
                        st.session_state.login_notice = message
                        st.session_state.unverified_email = None
                    else:
                        st.session_state.login_error = message
                    st.session_state.login_error_shown = False
                    st.rerun()
            elif st.session_state.login_error:
                _alert("error", f"<b>{escape(st.session_state.login_error)}</b>")
            st.session_state.login_error = None

            with st.form("login_form", border=False):
                email = st.text_input("Email", placeholder="you@example.com", key="email_login")
                password = st.text_input("Password", type="password", placeholder="Enter your password", key="password_login")
                submitted = st.form_submit_button("Sign in", type="primary", use_container_width=True)

            if submitted:
                errors = []
                if not email.strip():
                    errors.append("Email is required")
                elif "@" not in email or "." not in email:
                    errors.append("Please enter a valid email address")
                if not password:
                    errors.append("Password is required")

                if errors:
                    st.session_state.login_error = ". ".join(errors) + "."
                    st.session_state.unverified_email = None
                    st.rerun()
                else:
                    with st.spinner("Signing in..."):
                        success, message, user_data, email_not_verified = login_user(email.strip(), password)
                    if success:
                        st.session_state.logged_in = True
                        st.session_state.userId = user_data["id"]
                        st.session_state.user_name = user_data["full_name"]
                        st.session_state.user_email = user_data["email"]
                        st.session_state.user_photo = user_data.get("profile_photo_path")
                        st.session_state.onboarding_completed = user_data.get("onboarding_completed", True)
                        st.session_state.unverified_email = None
                        st.switch_page("main.py")
                    else:
                        if message == "Invalid email or password":
                            message = "Email or password is incorrect. Check them and try again, or reset your password."
                        st.session_state.login_error = message
                        st.session_state.unverified_email = email.strip() if email_not_verified else None
                        st.rerun()

            if st.button("Forgot password?", key="gm_login_forgot"):
                st.session_state.login_mode = "forgot"
                st.rerun()

            st.markdown('<div class="gm-login-divider">New to GAMASKILL?</div>', unsafe_allow_html=True)
            if st.button("Create an account", key="gm_login_register", use_container_width=True):
                st.switch_page("pages/register.py")

        form_bottom()
