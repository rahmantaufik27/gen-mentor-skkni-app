"""
Admin module shell: sidebar, header, and auth guard for the admin dashboard.

Deliberately separate from utils/theme.py's learner-facing NAV_ITEMS /
render_sidebar_nav / render_app_header, which are the LEARNER interface's
navigation - the admin module has its own session-state flag
(admin_logged_in, distinct from the learner's logged_in) and its own
section registry (see pages/admin_dashboard.py's ADMIN_SECTIONS), so it can
be extended with new admin features without touching learner code at all.

Visual basics (brand mark, avatar initials, CSS classes from
assets/css/main.css) are still reused from utils/theme.py - that's just the
shared design system, not learner logic.
"""

import streamlit as st

from utils.theme import render_brand, avatar_initials


def require_admin_authentication():
    """Stop the page from rendering unless an admin is logged in."""
    if not st.session_state.get("admin_logged_in"):
        st.warning("⚠️ Please sign in as an admin to access this page.")
        st.stop()


def render_admin_sidebar(active: str, sections: dict):
    """Render the admin sidebar: brand + the admin section registry."""
    with st.sidebar:
        render_brand()
        st.markdown('<div class="gm-nav-section-label">Admin</div>', unsafe_allow_html=True)
        for key, section in sections.items():
            is_active = active == key
            if st.button(
                section["label"],
                use_container_width=True,
                type="primary" if is_active else "secondary",
                key=f"admin_nav_{key}",
            ):
                st.session_state.admin_section = key
                st.rerun()


def render_admin_header(title: str) -> bool:
    """
    Render the admin top header: title on the left, admin chip + logout on the right.

    Returns:
        True if the Logout button was clicked this run (caller handles the
        actual session teardown, keeping auth logic out of this shell).
    """
    left, right = st.columns([3, 2])

    with left:
        st.markdown(f'<div class="gm-header-title">{title}</div>', unsafe_allow_html=True)

    admin_email = st.session_state.get("admin_email", "")
    logout_clicked = False
    with right:
        chip_col, btn_col = st.columns([3, 1])
        with chip_col:
            st.markdown(
                f"""
                <div class="gm-user-chip" style="justify-content:flex-end;">
                    <div class="gm-user-meta" style="text-align:right;">
                        <div class="gm-user-name">Admin</div>
                        <div class="gm-user-role">{admin_email}</div>
                    </div>
                    <div class="gm-avatar">{avatar_initials("Admin")}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with btn_col:
            logout_clicked = st.button(":material/logout:", key="admin_logout_btn", help="Logout")

    st.markdown('<hr style="margin-top: 10px;">', unsafe_allow_html=True)
    return logout_clicked
