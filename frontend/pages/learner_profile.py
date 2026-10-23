"""
Learner Profile Page - Main Hub with Navigation

This is the main application hub after login.
It provides navigation to:
- Test page (formerly "Quiz")
- Learning Path page (Reading Materials / Practice / Notes / Reflection /
  Discussion submenu)
- Account/Profile information
- Logout functionality

Also renders the floating Learning Assistant chatbot widget (see
components/chatbot_widget.py) on every page - it's not a menu entry.

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
from utils.auth_guard import get_current_user
from utils.theme import render_sidebar_nav, render_app_header
from utils.gating import get_learning_gating
from utils.profile_api import profile_photo_url
from components.mastery_dashboard import render_data_analytics, render_engagement
from components.user_profile import render_profile_landing
from components.learning_path import get_learning_path_submenu
from components.chatbot_widget import render_chatbot_widget

PAGE_TITLES = {
    "profile": ("My Profile", "Your overview, plus your account, password, and photo"),
    "onboarding": ("Onboarding", "Revisit the welcome tour and your SKKNI career path"),
    "data_analytics": ("Data Analytics", "Your Test and Practice performance"),
    "engagement": ("Engagement", "How consistently you're learning, and how you compare to peers"),
    "learning_path": ("Learning Path", "Curated resources based on your quiz results"),
    "reading_materials": ("Reading Materials", "Materials recommended based on your mastery gaps"),
    "practice": ("Practice with Generative Questions", "Adaptive practice questions for your weakest units"),
    "cue_questions": ("Cue Questions", "Saved question notes plus your own free-form question notes"),
    "key_points": ("Key Points", "Saved material and chat notes plus your own free-form notes"),
    "reflection_learning": ("Reflection Learning", "Turn today's learning into a concrete action plan"),
    "discussion": ("Discussion", "Ask and help each other out, unit by unit"),
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

user_photo_url = profile_photo_url(current_user["userId"]) if current_user.get("user_photo") else None
if render_app_header(
    title, subtitle, user_name=current_user.get("user_name") or "", user_email=current_user.get("user_email") or "",
    user_photo_url=user_photo_url,
):
    st.session_state.logged_in = False
    st.session_state.userId = None
    st.session_state.user_name = None
    st.session_state.user_email = None
    st.session_state.user_photo = None
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

elif st.session_state.current_page == "onboarding":
    # ====================================================================
    # ONBOARDING (re-entry from the sidebar) - same wizard main.py shows a
    # first-time login (see pages/onboarding.py). Its own finish/skip paths
    # already set current_page and st.rerun() when done, same as a first run.
    # ====================================================================
    try:
        with open("pages/onboarding.py", "r", encoding="utf-8") as f:
            exec(f.read())
    except Exception as e:
        st.error(f"Failed to load Onboarding page: {str(e)}")

elif st.session_state.current_page == "data_analytics":
    # ====================================================================
    # DATA ANALYTICS PAGE (Pre-Test / Practice / Post-Test - split out of
    # My Profile, see components/mastery_dashboard.py::render_data_analytics)
    # ====================================================================
    render_data_analytics()

elif st.session_state.current_page == "engagement":
    # ====================================================================
    # ENGAGEMENT PAGE (streaks, peer benchmark, badges - split out of
    # Data Analytics' old 4th tab, see
    # components/mastery_dashboard.py::render_engagement)
    # ====================================================================
    render_engagement()

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

elif st.session_state.current_page == "discussion":
    # ====================================================================
    # DISCUSSION PAGE (Learning Path -> Discussion)
    # ====================================================================
    try:
        with open("pages/discussion.py", "r", encoding="utf-8") as f:
            exec(f.read())
    except Exception as e:
        st.error(f"Failed to load Discussion page: {str(e)}")

else:  # profile (default)
    # ====================================================================
    # MY PROFILE PAGE - the post-login landing page: an Overview tab
    # (greeting, nudge banner, quick links) plus an Update Profile tab
    # (identity, photo, password) - see components/user_profile.py
    # ====================================================================
    render_profile_landing()

# ============================================================================
# LEARNING ASSISTANT FLOATING WIDGET - rendered last (position:fixed via CSS
# lifts it out of normal page flow regardless of DOM order) and OUTSIDE the
# page branching above, so it's visible on every page, not just one menu
# entry - see components/chatbot_widget.py for why.
# ============================================================================
render_chatbot_widget()
