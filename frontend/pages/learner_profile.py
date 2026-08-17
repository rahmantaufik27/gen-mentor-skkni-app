"""
Learner Profile Page - Main Hub with Navigation

This is the main application hub after login.
It provides navigation to:
- Test page (formerly "Quiz")
- Learning Path page (Reading Materials / Chatbot / Practice submenu)
- Account/Profile information
- Logout functionality

Test and Practice eligibility is gated (see utils/gating.py): the Test
(the Placement Test) is taken exactly once, ever - eligible only before
that one attempt, permanently ineligible afterward. Practice becomes
eligible from that point on, for the rest of the user's lifetime. Both
stay visible/clickable in the sidebar at all times - the gate only
disables the Start button on each page, with an inline message explaining
why (see pages/test.py / components/practice.py).

NOTE: main.py handles authentication check, st.set_page_config(), and theme
injection. This code is exec'd by main.py, so don't duplicate those calls.
"""

import streamlit as st
from utils.state import save_persistent_state
from utils.auth_guard import get_current_user
from utils.theme import render_sidebar_nav, render_app_header
from utils.gating import get_learning_gating
from components.mastery_dashboard import render_mastery_dashboard
from components.learning_path import get_learning_path_submenu

PAGE_TITLES = {
    "profile": ("My Profile", "Your account and mastery-level overview"),
    "learning_path": ("Learning Path", "Curated resources based on your quiz results"),
    "reading_materials": ("Reading Materials", "Materials recommended based on your mastery gaps"),
    "chatbot": ("Learning with Chatbot Assistance", "Chat with an AI tutor for personalized help"),
    "practice": ("Practice with Generative Questions", "Adaptive practice questions for your weakest units"),
    "cue_questions": ("Cue Questions", "Saved question notes plus your own free-form question notes"),
    "key_points": ("Key Points", "Saved material and chat notes plus your own free-form notes"),
    "reflection_learning": ("Reflection Learning", "Turn today's learning into a concrete action plan"),
    "test": ("Test", "Test your knowledge across all six units"),
}
# Admin is a separate module (pages/admin_login.py + pages/admin_dashboard.py)
# with its own login - deliberately not part of this learner hub's routing.

# ============================================================================
# INITIALIZE PAGE SELECTION
# ============================================================================
if "current_page" not in st.session_state:
    st.session_state.current_page = "profile"

# ============================================================================
# TEST / PRACTICE ELIGIBILITY (see utils/gating.py) - the Test (the
# Placement Test) is eligible only before it's ever been taken; Practice
# becomes eligible from then on, for good (a Test can never be retaken).
# Used below for the Placement Test header and passed to each page, which
# disables its own Start button rather than the sidebar entry -
# Test/Practice stay visible and clickable at all times.
# ============================================================================
gating = get_learning_gating()

# ============================================================================
# LEFT NAVIGATION SIDEBAR
# ============================================================================
render_sidebar_nav(
    active=st.session_state.current_page,
    submenus={"learning_path": get_learning_path_submenu()},
)

# ============================================================================
# TOP HEADER (title + user chip + logout)
# ============================================================================
current_user = get_current_user()
if st.session_state.current_page == "test" and gating["is_placement_test"]:
    title, subtitle = "Placement Test (Pre-Test)", "Your first Test assesses your starting knowledge across all six units"
elif st.session_state.current_page == "test" and (gating.get("test_stage") == "post" or gating.get("post_test_completed")):
    title, subtitle = "Post-Test", "A final Test across all six units to confirm the progress you made in Practice"
else:
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

if st.session_state.current_page == "test":
    # ====================================================================
    # TEST PAGE
    # ====================================================================
    try:
        with open("pages/test.py", "r", encoding="utf-8") as f:
            exec(f.read())
    except Exception as e:
        st.error(f"Failed to load Test page: {str(e)}")

elif st.session_state.current_page == "learning_path":
    # ====================================================================
    # LEARNING PATH PAGE (landing page - submenu items below are their own
    # dedicated full pages, not rendered here)
    # ====================================================================
    try:
        with open("pages/learning_path.py", "r", encoding="utf-8") as f:
            exec(f.read())
    except Exception as e:
        st.error(f"Failed to load Learning Path page: {str(e)}")

elif st.session_state.current_page == "reading_materials":
    # ====================================================================
    # READING MATERIALS PAGE
    # ====================================================================
    try:
        with open("pages/reading_materials.py", "r", encoding="utf-8") as f:
            exec(f.read())
    except Exception as e:
        st.error(f"Failed to load Reading Materials page: {str(e)}")

elif st.session_state.current_page == "chatbot":
    # ====================================================================
    # LEARNING WITH CHATBOT ASSISTANCE PAGE
    # ====================================================================
    try:
        with open("pages/chatbot.py", "r", encoding="utf-8") as f:
            exec(f.read())
    except Exception as e:
        st.error(f"Failed to load Chatbot page: {str(e)}")

elif st.session_state.current_page == "practice":
    # ====================================================================
    # PRACTICE WITH GENERATIVE QUESTIONS PAGE
    # ====================================================================
    try:
        with open("pages/practice.py", "r", encoding="utf-8") as f:
            exec(f.read())
    except Exception as e:
        st.error(f"Failed to load Practice page: {str(e)}")

elif st.session_state.current_page == "cue_questions":
    # ====================================================================
    # CUE QUESTIONS PAGE (Learning Path -> Cue Questions)
    # ====================================================================
    try:
        with open("pages/cue_questions.py", "r", encoding="utf-8") as f:
            exec(f.read())
    except Exception as e:
        st.error(f"Failed to load Cue Questions page: {str(e)}")

elif st.session_state.current_page == "key_points":
    # ====================================================================
    # KEY POINTS PAGE (Learning Path -> Key Points)
    # ====================================================================
    try:
        with open("pages/key_points.py", "r", encoding="utf-8") as f:
            exec(f.read())
    except Exception as e:
        st.error(f"Failed to load Key Points page: {str(e)}")

elif st.session_state.current_page == "reflection_learning":
    # ====================================================================
    # REFLECTION LEARNING PAGE (Learning Path -> Reflection Learning)
    # ====================================================================
    try:
        with open("pages/reflection_learning.py", "r", encoding="utf-8") as f:
            exec(f.read())
    except Exception as e:
        st.error(f"Failed to load Reflection Learning page: {str(e)}")

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

    # Display Test Analytics + Practice Analytics dashboard (each section
    # owns its own bordered container/header - see components/mastery_dashboard.py)
    render_mastery_dashboard()
