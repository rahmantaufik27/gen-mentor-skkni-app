"""
Notes Page (Learning Path -> Notes)

Route Protection:
- Requires authentication (redirects to login if not authenticated)

Dedicated full page for the user's saved notes/bookmarks - reachable from the
Learning Path submenu in the sidebar. Renders components/notes.py::render_notes()
(backed by /api/notes/*, its own user_notes table). Independent of the
Test/Practice/mastery logic - see components/learning_path.py.
"""

import streamlit as st
from utils.auth_guard import require_authentication
from components.learning_path import LEARNING_METHODS

# ============================================================================
# ROUTE PROTECTION - Require Authentication
# ============================================================================
require_authentication()

with st.container(border=True):
    LEARNING_METHODS["notes"]["render"]()
