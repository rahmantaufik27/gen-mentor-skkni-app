"""
Exercises with Generative Questions Page

Route Protection:
- Requires authentication (redirects to login if not authenticated)
- Only accessible to authenticated users

Dedicated full page for the Exercises with Generative Questions learning
method - reachable directly from the Learning Path submenu in the sidebar.
Recommendation logic is unchanged - see components/exercises.py, backed by
the existing GET /api/quiz/recommended-questions endpoint.
"""

import streamlit as st
from utils.auth_guard import require_authentication
from components.learning_path import LEARNING_METHODS

# ============================================================================
# ROUTE PROTECTION - Require Authentication
# ============================================================================
require_authentication()

with st.container(border=True):
    LEARNING_METHODS["exercises"]["render"]()
