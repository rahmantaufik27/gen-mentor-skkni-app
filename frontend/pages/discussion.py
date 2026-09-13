"""
Discussion Page (Learning Path -> Discussion)

Route Protection:
- Requires authentication (redirects to login if not authenticated)

Dedicated full page for the peer discussion forum - reachable from the
Learning Path submenu in the sidebar. Renders
components/discussion.py::render_discussion(), backed by the
/api/discussions/* endpoints and its own unit_discussion_posts table (see
services/discussion_service.py) - independent of every other Learning Path
module.
"""

import streamlit as st
from utils.auth_guard import require_authentication
from components.learning_path import LEARNING_METHODS

# ============================================================================
# ROUTE PROTECTION - Require Authentication
# ============================================================================
require_authentication()

with st.container(border=True):
    LEARNING_METHODS["discussion"]["render"]()
