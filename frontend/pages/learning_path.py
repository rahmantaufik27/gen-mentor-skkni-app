"""
Learning Path Page

Route Protection:
- Requires authentication (redirects to login if not authenticated)
- Only accessible to authenticated users
- Displays learning materials and resources
"""

import streamlit as st
from utils.state import save_persistent_state
from utils.auth_guard import require_authentication
from utils.practice_api import get_practice_analytics, get_learning_path_stats, record_activity, record_material_view, record_chatbot_attempt

# ============================================================================
# ROUTE PROTECTION - Require Authentication
# ============================================================================
require_authentication()

def render_learning_path_page():
    """
    Render the learning path page with learning materials.
    """
    with st.container(border=True):
        st.markdown("#### 📚 Learning Materials & Resources")
        st.markdown("""
            This section tracking your progress learning and provides curated learning materials to help close the gaps
            identified by your test results:
            - Reading materials organized by unit
            - Learning with Chatbot Assistance
            - Practices with Generative Questions
        """)

    analytics = get_practice_analytics()
    if not analytics.get("success"):
        st.error(f"Failed to load Practice Analytics: {analytics.get('error', 'Unknown error')}")
        return

    stats = get_learning_path_stats()
    if not stats.get("success"):
        st.error(f"Failed to load Learning Path Stats: {stats.get('error', 'Unknown error')}")
        return

    total_sessions = analytics.get("total_sessions", 0)
    total_materials_viewed = stats.get("materials_viewed", 0)
    latest_practice_score = stats.get("latest_practice_score", 0)
    average_practice_score = stats.get("average_practice_score", 0)

    with st.container(border=True):
        # Learning statistics
        st.markdown("###### Your Progress")
        
        col1, col2, col3 = st.columns(3)
        # col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                label="Materials Completed",
                value=str(total_materials_viewed),
                help="Number of learning materials completed"
            )
        
        with col2:
            st.metric(
                label="Average Practice Score Percentage",
                value=f"{average_practice_score}%",
                help="Your average score on practice exercises"
            )

        with col3:
            st.metric(
                label="Total Practice Sessions",
                value=str(total_sessions),
                help="Number of practice sessions you have completed"
            )
        
        st.info("Complete a Test first to get personalized learning recommendations.")

    with st.container(border=True):
        st.markdown("###### Get Started")
        st.info(
            "👈 Choose a learning method from the sidebar: **Reading Materials**, "
            "**Learning with Chatbot Assistance**, or **Practice with Generative Questions**."
        )

# Render the page
render_learning_path_page()
