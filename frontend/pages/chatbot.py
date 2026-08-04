"""
Learning with Chatbot Assistance Page

Route Protection:
- Requires authentication (redirects to login if not authenticated)
- Only accessible to authenticated users

Dedicated full page for the Learning with Chatbot Assistance learning
method - reachable directly from the Learning Path submenu in the sidebar.
Placeholder for future LLM integration - see components/learning_path.py.
"""

import streamlit as st
from utils.auth_guard import require_authentication
from components.learning_path import LEARNING_METHODS

# ============================================================================
# ROUTE PROTECTION - Require Authentication
# ============================================================================
require_authentication()

with st.container(border=True):
    LEARNING_METHODS["chatbot"]["render"]()
