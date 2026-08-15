"""
Reflection Learning Page (Learning Path -> Reflection Learning)

Route Protection:
- Requires authentication (redirects to login if not authenticated)

Dedicated full page for the "Reflection & Action Plan" section (Immediate
Application, Challenges Expected, Next Learning Action, Motivation Rating) -
moved out of the Notes page into its own page, reachable from the Learning
Path submenu in the sidebar. Renders
components/reflection_learning.py::render_reflection_learning(), backed by
the same /api/reflection/* endpoints and user_reflections table as the "Cue
Questions & Key Points" section still shown on Notes - same config, same
API, same table, so no reflection data was moved, duplicated, or lost.
"""

import streamlit as st
from utils.auth_guard import require_authentication
from components.learning_path import LEARNING_METHODS

# ============================================================================
# ROUTE PROTECTION - Require Authentication
# ============================================================================
require_authentication()

with st.container(border=True):
    LEARNING_METHODS["reflection_learning"]["render"]()
