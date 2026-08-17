"""
Cue Questions Page (Learning Path -> Cue Questions)

Route Protection:
- Requires authentication (redirects to login if not authenticated)

Dedicated full page for saved Practice Question bookmarks ("Cue Question"
tab, moved from the former Notes page unchanged) plus user-authored WYSIWYG
notes about questions ("Free Question" tab, new) - reachable from the
Learning Path submenu in the sidebar. Renders
components/cue_questions.py::render_cue_questions().
"""

import streamlit as st
from utils.auth_guard import require_authentication
from components.learning_path import LEARNING_METHODS

# ============================================================================
# ROUTE PROTECTION - Require Authentication
# ============================================================================
require_authentication()

with st.container(border=True):
    LEARNING_METHODS["cue_questions"]["render"]()
