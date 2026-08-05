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
            This section provides curated learning materials to help close the gaps
            identified by your test results:
            - Tracking Progress Learning
            - Reading materials organized by unit
            - Learning with Chatbot Assistance
        """)

    with st.container(border=True):
        # Learning statistics
        st.markdown("###### Your Progress")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                label="Topics Studied",
                value="0",
                help="Number of topics you have studied"
            )
        
        with col2:
            st.metric(
                label="Materials Completed",
                value="0",
                help="Number of learning materials completed"
            )
        
        with col3:
            st.metric(
                label="Practice Score",
                value="0%",
                help="Your average score on practice exercises"
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
