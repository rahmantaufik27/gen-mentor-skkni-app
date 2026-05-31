"""User Login Page"""

import streamlit as st
import httpx
import config
from utils.state import load_persistent_state, save_persistent_state

# Initialize session state
if "login_error" not in st.session_state:
    st.session_state.login_error = None

st.set_page_config(page_title="Login - Gen-Mentor", page_icon="🔐", layout="centered")
# st.logo("./assets/avatar.png")

# Custom CSS
st.markdown('''
    <style>
    .login-container {
        max-width: 500px;
        margin: 0 auto;
    }
    .error-message {
        padding: 10px;
        border-radius: 5px;
        background-color: #f8d7da;
        color: #721c24;
        border: 1px solid #f5c6cb;
        margin-bottom: 20px;
    }
    </style>
''', unsafe_allow_html=True)


def login_user(email: str, password: str):
    """Authenticate user with the backend."""
    try:
        backend_url = config.backend_endpoint
        endpoint = f"{backend_url}api/auth/login"
        
        # Prepare request data
        data = {
            "email": email,
            "password": password
        }
        
        # Make request to backend
        with httpx.Client(timeout=10) as client:
            response = client.post(endpoint, json=data)
        
        if response.status_code == 200:
            result = response.json()
            user_data = result.get("user", {})
            return True, "Login successful", user_data
        else:
            result = response.json()
            error_msg = result.get("error", "Login failed")
            return False, error_msg, None
            
    except httpx.ConnectError:
        return False, "Cannot connect to backend server. Make sure it's running on localhost:5000", None
    except Exception as e:
        return False, f"Error: {str(e)}", None


# Page title and description
st.markdown("<h1 style='text-align: center;'>Welcome Back</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>Sign in to your Gen-Mentor account</p>", unsafe_allow_html=True)
st.divider()

# Display error message if there was one
if st.session_state.login_error:
    st.error(st.session_state.login_error)
    st.session_state.login_error = None

# Login form
with st.form("login_form"):
    email = st.text_input(
        "Email",
        placeholder="your@email.com",
        key="email_login"
    )
    
    password = st.text_input(
        "Password",
        type="password",
        placeholder="Enter your password",
        key="password_login"
    )
    
    # Form submission
    submitted = st.form_submit_button(
        "Sign In",
        type="primary",
        use_container_width=True
    )
    
    if submitted:
        # Validate inputs
        errors = []
        
        if not email.strip():
            errors.append("Email is required")
        elif "@" not in email or "." not in email:
            errors.append("Please enter a valid email address")
        
        if not password:
            errors.append("Password is required")
        
        if errors:
            for error in errors:
                st.error(f"• {error}")
        else:
            # Show loading spinner
            with st.spinner("Signing in..."):
                success, message, user_data = login_user(email.strip(), password)
            
            if success:
                # Store user info in session state
                st.session_state.logged_in = True
                st.session_state.userId = user_data["id"]
                st.session_state.user_name = user_data["full_name"]
                st.session_state.user_email = user_data["email"]
                
                # Save state
                save_persistent_state()
                
                st.success(message)
                # Redirect to main app or dashboard
                import time
                time.sleep(1)
                st.switch_page("pages/learner_profile.py")
            else:
                st.session_state.login_error = message
                st.rerun()

# Don't have an account?
st.divider()
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    if st.button("Create Account", use_container_width=True):
        st.switch_page("pages/register.py")

# Forgot password
st.markdown("---")
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    st.markdown("*Forgot password? (Coming soon)*", unsafe_allow_html=True)
