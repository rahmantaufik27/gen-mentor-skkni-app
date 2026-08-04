"""
Reading Materials Page

Route Protection:
- Requires authentication (redirects to login if not authenticated)
- Only accessible to authenticated users

Dedicated full page for the Reading Materials learning method - reachable
directly from the Learning Path submenu in the sidebar (always visible, not
nested inside the Learning Path page). Rendering/recommendation logic is
unchanged - see components/reading_materials.py.
"""

import streamlit as st
from utils.auth_guard import require_authentication
from components.learning_path import LEARNING_METHODS

# ============================================================================
# ROUTE PROTECTION - Require Authentication
# ============================================================================
require_authentication()

with st.container(border=True):
    LEARNING_METHODS["reading_materials"]["render"]()
