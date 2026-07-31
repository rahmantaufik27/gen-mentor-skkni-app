"""
Learner Profile Page - Main Hub with Navigation

This is the main application hub after login.
It provides navigation to:
- Quiz page
- Learning Path page
- Account/Profile information
- Logout functionality

NOTE: main.py handles authentication check and st.set_page_config()
This code is exec'd by main.py, so don't duplicate those calls.
"""

import streamlit as st
from utils.state import save_persistent_state
from utils.auth_guard import get_current_user
from components.mastery_dashboard import render_mastery_dashboard

# ============================================================================
# CUSTOM NAVIGATION MENU (at top)
# ============================================================================
st.markdown("---")

# Navigation tabs
nav_col1, nav_col2, nav_col3, nav_col4 = st.columns(4)

with nav_col1:
    if st.button(":material/account_circle: My Profile", use_container_width=True, key="nav_profile"):
        st.session_state.current_page = "profile"
        st.rerun()

with nav_col2:
    if st.button(":material/school: Learning Path", use_container_width=True, key="nav_learning"):
        st.session_state.current_page = "learning_path"
        st.rerun()

with nav_col3:
    if st.button(":material/assignment: Quiz", use_container_width=True, key="nav_quiz"):
        st.session_state.current_page = "quiz"
        st.rerun()

with nav_col4:
    if st.button(":material/logout: Logout", use_container_width=True, key="nav_logout"):
        st.session_state.logged_in = False
        st.session_state.userId = None
        st.session_state.user_name = None
        st.session_state.user_email = None
        save_persistent_state()
        st.success("✅ Logged out successfully!")
        st.rerun()

st.markdown("---")

# ============================================================================
# INITIALIZE PAGE SELECTION
# ============================================================================
if "current_page" not in st.session_state:
    st.session_state.current_page = "profile"

# ============================================================================
# RENDER SELECTED PAGE
# ============================================================================

if st.session_state.current_page == "quiz":
    # ====================================================================
    # QUIZ PAGE
    # ====================================================================
    try:
        with open("pages/quiz.py", "r", encoding="utf-8") as f:
            exec(f.read())
    except Exception as e:
        st.error(f"Failed to load Quiz page: {str(e)}")

elif st.session_state.current_page == "learning_path":
    # ====================================================================
    # LEARNING PATH PAGE
    # ====================================================================
    st.title("🎓 Learning Path")
    st.divider()
    
    st.markdown("""
    ### Learning Materials & Resources
    
    This section will provide:
    - Learning materials organized by unit
    - Video tutorials
    - Reading materials
    - Practice exercises
    - Progress tracking
    
    Start by taking the Quiz to identify your learning gaps.
    """)
    
    with st.container(border=True):
        st.markdown("#### 📚 Available Units")
        st.info("Complete quizzes first to get personalized learning recommendations.")

else:  # profile (default)
    # ====================================================================
    # LEARNER PROFILE PAGE
    # ====================================================================
    st.title("👤 My Profile")
    st.divider()
    
    # Get current user information
    current_user = get_current_user()
    
    # Display user information section
    with st.container(border=True):
        st.markdown("#### Account Information")
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Name:** {current_user['user_name']}")
        with col2:
            st.write(f"**Email:** {current_user['user_email']}")
    
    st.divider()
    
    # Display mastery-level dashboard
    st.markdown("#### 📊 Mastery Level Dashboard")
    render_mastery_dashboard()

