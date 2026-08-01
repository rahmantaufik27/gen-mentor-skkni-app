"""
Learner Profile Page - Main Hub with Navigation

This is the main application hub after login.
It provides navigation to:
- Quiz page
- Learning Path page
- Account/Profile information
- Logout functionality

NOTE: main.py handles authentication check, st.set_page_config(), and theme
injection. This code is exec'd by main.py, so don't duplicate those calls.
"""

import streamlit as st
from utils.state import save_persistent_state
from utils.auth_guard import get_current_user
from utils.theme import render_sidebar_nav, render_app_header
from components.mastery_dashboard import render_mastery_dashboard
from components.learning_path import render_learning_path

PAGE_TITLES = {
    "profile": ("My Profile", "Your account and mastery-level overview"),
    "learning_path": ("Learning Path", "Curated resources based on your quiz results"),
    "quiz": ("Quiz Assessment", "Test your knowledge across all six units"),
}

# ============================================================================
# INITIALIZE PAGE SELECTION
# ============================================================================
if "current_page" not in st.session_state:
    st.session_state.current_page = "profile"

# ============================================================================
# LEFT NAVIGATION SIDEBAR
# ============================================================================
render_sidebar_nav(active=st.session_state.current_page)

# ============================================================================
# TOP HEADER (title + user chip + logout)
# ============================================================================
current_user = get_current_user()
title, subtitle = PAGE_TITLES.get(st.session_state.current_page, PAGE_TITLES["profile"])

if render_app_header(title, subtitle, user_name=current_user.get("user_name") or "", user_email=current_user.get("user_email") or ""):
    st.session_state.logged_in = False
    st.session_state.userId = None
    st.session_state.user_name = None
    st.session_state.user_email = None
    save_persistent_state()
    st.success("✅ Logged out successfully!")
    st.rerun()

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
    try:
        with open("pages/learning_path.py", "r", encoding="utf-8") as f:
            exec(f.read())
    except Exception as e:
        st.error(f"Failed to load Learning Path page: {str(e)}")
    # with st.container(border=True):
    #     st.markdown("""
    #         #### 📚 Learning Materials & Resources

    #         This section provides curated learning materials to help close the gaps
    #         identified by your quiz results:

    #         - Reading materials organized by unit
    #         - Learning with Chatbot Assistance
    #         - Tracking Progress Learning

    #     """)

    #     st.info("Complete quizzes first to get personalized learning recommendations.")

    # with st.container(border=True):
    #     render_learning_path()

else:  # profile (default)
    # ====================================================================
    # LEARNER PROFILE PAGE
    # ====================================================================
    # # Display user information section
    # with st.container(border=True):
    #     st.markdown("#### Account Information")
    #     col1, col2 = st.columns(2)
    #     with col1:
    #         st.write(f"**Name:** {current_user['user_name']}")
    #     with col2:
    #         st.write(f"**Email:** {current_user['user_email']}")

    # st.markdown("")

    # Display mastery-level dashboard
    with st.container(border=True):
        st.markdown("#### 📊 Mastery Level Dashboard")
        render_mastery_dashboard()
