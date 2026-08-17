"""
Key Points Page (Learning Path -> Key Points)

Route Protection:
- Requires authentication (redirects to login if not authenticated)

Dedicated full page for saved Reading Material and Chatbot Discussion
bookmarks ("Materials"/"Chat" tabs, moved from the former Notes page
unchanged) plus user-authored WYSIWYG notes ("Free Notes" tab, new) -
reachable from the Learning Path submenu in the sidebar. Renders
components/key_points.py::render_key_points().
"""

import streamlit as st
from utils.auth_guard import require_authentication
from components.learning_path import LEARNING_METHODS

# ============================================================================
# ROUTE PROTECTION - Require Authentication
# ============================================================================
require_authentication()

with st.container(border=True):
    LEARNING_METHODS["key_points"]["render"]()
