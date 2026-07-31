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


def render_learning_path():
    """
    Render the learning path page with learning materials.
    """
    st.title("📚 Learning Path")
    st.divider()
    
    st.markdown("""
    ### Welcome to Your Learning Path
    
    This section provides you with curated learning materials to help you master the topics covered in the quizzes.
    
    #### Available Resources:
    - **Tutorial Videos**: Step-by-step video guides
    - **Reading Materials**: Detailed articles and documentation
    - **Practice Exercises**: Interactive exercises to reinforce learning
    - **Code Examples**: Real-world code samples and patterns
    
    #### How to Use:
    1. Start with the **Quiz** section to test your knowledge
    2. Identify areas where you need improvement
    3. Use this Learning Path to study those topics
    4. Return to Quiz to verify your learning progress
    
    """)
    
    st.divider()
    
    # Placeholder for learning materials
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        #### 🎥 Video Tutorials
        Coming soon! Video tutorials covering key concepts will be available here.
        """)
    
    with col2:
        st.markdown("""
        #### 📖 Reading Materials  
        Coming soon! Comprehensive reading materials will be available here.
        """)
    
    st.divider()
    
    # Learning statistics
    st.markdown("#### 📊 Your Progress")
    
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
    
    st.divider()
    
    # Learning resources
    st.markdown("#### 🔗 Quick Links")
    st.info("Take a quiz first to see recommended learning materials based on your results.")


# Render the page
render_learning_path()
