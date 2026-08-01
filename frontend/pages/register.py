"""User Registration Page"""

import streamlit as st
import httpx
import config
from utils.state import load_persistent_state, save_persistent_state
from utils.theme import inject_theme, render_brand

# Initialize session state
if "registration_success" not in st.session_state:
    st.session_state.registration_success = False

if "registration_error" not in st.session_state:
    st.session_state.registration_error = None

st.set_page_config(page_title="Register - Gen-Mentor", page_icon="📝", layout="centered", initial_sidebar_state="collapsed")

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

def register_user(full_name: str, email: str, password: str, confirm_password: str):
    """Register a new user with the backend."""
    try:
        backend_url = config.backend_endpoint
        endpoint = f"{backend_url}api/auth/register"
        
        # Prepare request data
        data = {
            "full_name": full_name,
            "email": email,
            "password": password,
            "confirm_password": confirm_password
        }
        
        # Make request to backend
        with httpx.Client(timeout=10) as client:
            response = client.post(endpoint, json=data)
        
        if response.status_code == 201:
            result = response.json()
            return True, result.get("message", "Registration successful!")
        else:
            result = response.json()
            error_msg = result.get("error", "Registration failed")
            return False, error_msg
            
    except httpx.ConnectError:
        return False, "Cannot connect to backend server. Make sure it's running on localhost:5000"
    except Exception as e:
        return False, f"Error: {str(e)}"


render_brand(auth_style=True)

with st.container(border=True):
    # Page title and description
    st.markdown("<h2 style='text-align: center; margin-top:0;'>Create Your Account</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: var(--text-muted);'>Join Gen-Mentor and start your learning journey</p>", unsafe_allow_html=True)

    # Display success message if registration was successful
    if st.session_state.registration_success:
        st.success("✓ Registration successful! Redirecting to login page...")
        import time
        time.sleep(2)
        st.session_state.registration_just_completed = True
        st.switch_page("pages/login.py")

    # Display error message if there was an error
    if st.session_state.registration_error:
        st.error(st.session_state.registration_error)
        st.session_state.registration_error = None

    # Registration form
    with st.form("registration_form"):
        full_name = st.text_input(
            "Full Name",
            placeholder="John Doe",
            key="full_name_register"
        )

        email = st.text_input(
            "Email",
            placeholder="john@example.com",
            key="email_register"
        )

        password = st.text_input(
            "Password",
            type="password",
            placeholder="At least 8 characters",
            key="password_register"
        )

        confirm_password = st.text_input(
            "Confirm Password",
            type="password",
            placeholder="Re-enter your password",
            key="confirm_password_register"
        )

        # Form submission
        submitted = st.form_submit_button(
            "Create Account",
            type="primary",
            use_container_width=True
        )

        if submitted:
            # Validate inputs
            errors = []

            if not full_name.strip():
                errors.append("Full name is required")
            if not email.strip():
                errors.append("Email is required")
            elif "@" not in email or "." not in email:
                errors.append("Please enter a valid email address")
            if not password:
                errors.append("Password is required")
            elif len(password) < 8:
                errors.append("Password must be at least 8 characters")
            if password != confirm_password:
                errors.append("Passwords do not match")

            if errors:
                for error in errors:
                    st.error(f"• {error}")
            else:
                # Show loading spinner
                with st.spinner("Creating your account..."):
                    success, message = register_user(full_name.strip(), email.strip(), password, confirm_password)

                if success:
                    st.session_state.registration_success = True
                    st.rerun()
                else:
                    st.session_state.registration_error = message
                    st.rerun()

    st.caption("Password must be at least 8 characters. Uppercase, lowercase, and numbers are recommended.")

# Already have an account?
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("Already have an account? Login", use_container_width=True):
        st.switch_page("pages/login.py")
