"""
Authentication Guard Utility

Provides helper functions for protecting routes and managing authentication state.
"""

import streamlit as st


def require_authentication():
    """
    Authentication Guard - Stops execution if user not authenticated.
    Call this at the start of any protected page.
    
    Main.py will automatically redirect unauthenticated users to login.
    This function just prevents the page from rendering.
    
    Usage:
        import streamlit as st
        from utils.auth_guard import require_authentication
        
        require_authentication()  # This will stop if user not logged in
        # Rest of page code here
    """
    if not st.session_state.get("logged_in"):
        st.warning("⚠️ Please login to access this page.")
        st.stop()
    return True


def is_authenticated() -> bool:
    """
    Check if user is authenticated.
    
    Returns:
        bool: True if user is logged in, False otherwise
    """
    return st.session_state.get("logged_in", False)


def get_current_user() -> dict:
    """
    Get current authenticated user information.
    
    Returns:
        dict: User data with keys: userId, user_name, user_email
              Returns empty dict if not authenticated
    """
    if is_authenticated():
        return {
            "userId": st.session_state.get("userId"),
            "user_name": st.session_state.get("user_name"),
            "user_email": st.session_state.get("user_email"),
        }
    return {}


def logout_user():
    """
    Logout the current user.
    Clears authentication state and triggers rerun.
    Main.py will redirect to login on next render.
    """
    # Clear authentication state
    st.session_state.logged_in = False
    st.session_state.userId = None
    st.session_state.user_name = None
    st.session_state.user_email = None
    
    # Save state
    from utils.state import save_persistent_state
    save_persistent_state()
    
    st.success("✅ Logged out successfully!")
    st.rerun()
