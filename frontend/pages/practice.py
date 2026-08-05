"""
Practice with Generative Questions Page

Route Protection:
- Requires authentication (redirects to login if not authenticated)
- Only accessible to authenticated users

Dedicated full page for the Practice learning method - reachable directly
from the Learning Path submenu in the sidebar. Test/Practice eligibility
(see utils/gating.py) is enforced inside components/practice.py's start
screen: the page and sidebar menu stay visible/clickable, and only the
Start button is disabled (with an inline message) when not eligible.
"""

import streamlit as st
from utils.auth_guard import require_authentication
from components.learning_path import LEARNING_METHODS

# ============================================================================
# ROUTE PROTECTION - Require Authentication
# ============================================================================
require_authentication()

with st.container(border=True):
    LEARNING_METHODS["practice"]["render"]()
