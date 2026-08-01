"""
Shared design-system utility: one place that owns the color palette,
CSS injection, and the reusable header/sidebar/avatar snippets so every
page renders a consistent look instead of duplicating markup or CSS.
"""

import streamlit as st

# Brand palette - must stay in sync with the CSS variables in assets/css/main.css
PRIMARY = "#FF0000"
ACCENT = "#FFD700"
SUCCESS = "#008000"
BACKGROUND = "#F8FAFC"
CARD = "#FFFFFF"
TEXT = "#111827"
BORDER = "#E5E7EB"

BRAND_NAME = "GenQ-SKKNI"

# Sidebar nav entries -> maps directly to st.session_state.current_page values
# consumed by pages/learner_profile.py
NAV_ITEMS = [
    {"key": "profile", "label": "My Profile", "icon": ":material/account_circle:"},
    {"key": "learning_path", "label": "Learning Path", "icon": ":material/school:"},
    {"key": "quiz", "label": "Quiz", "icon": ":material/assignment:"},
]


def inject_theme():
    """Load the shared stylesheet. Safe to call from every page/section."""
    try:
        with open("./assets/css/main.css", "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except Exception:
        pass


def avatar_initials(name: str) -> str:
    """Return 1-2 letter initials for an avatar badge."""
    if not name:
        return "?"
    parts = [p for p in name.strip().split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def render_brand(auth_style: bool = False):
    """Render the brand lockup (logo mark + name) used in the sidebar and auth pages."""
    wrapper_class = "gm-auth-brand" if auth_style else "gm-brand"
    st.markdown(
        f"""
        <div class="{wrapper_class}">
            <div class="gm-brand-mark">🎓</div>
            <div class="{'gm-auth-brand-text' if auth_style else 'gm-brand-text'}">{BRAND_NAME}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_nav(active: str):
    """
    Render the left navigation sidebar (brand + nav items).
    Sets st.session_state.current_page and reruns on click - same behavior
    as the previous top-nav bar, just relocated into a real left sidebar.
    """
    with st.sidebar:
        render_brand()
        st.markdown('<div class="gm-nav-section-label">Menu</div>', unsafe_allow_html=True)
        for item in NAV_ITEMS:
            is_active = active == item["key"]
            if st.button(
                f"{item['icon']} {item['label']}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
                key=f"nav_{item['key']}",
            ):
                st.session_state.current_page = item["key"]
                st.rerun()


def render_app_header(title: str, subtitle: str = "", user_name: str = "", user_email: str = "",show_logout: bool = True) -> bool:
    """
    Render the top header: page title on the left, user chip + logout on the right.

    Returns:
        True if the Logout button was clicked this run (caller handles the
        actual session teardown, keeping auth logic out of this utility).
    """
    left, right = st.columns([3, 2])

    with left:
        subtitle_html = f'<div class="gm-header-subtitle">{subtitle}</div>' if subtitle else ""
        st.markdown(
            f"""
            <div>
                <div class="gm-header-title">{title}</div>
                {subtitle_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    logout_clicked = False
    with right:
        if user_name:
            chip_col, btn_col = st.columns([3, 1])
            with chip_col:
                st.markdown(
                    f"""
                    <div class="gm-user-chip" style="justify-content:flex-end;">
                        <div class="gm-user-meta" style="text-align:right;">
                            <div class="gm-user-name">{user_name}</div>
                            <div class="gm-user-role">{user_email}</div>
                        </div>
                        <div class="gm-avatar">{avatar_initials(user_name)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with btn_col:
                if show_logout:
                    logout_clicked = st.button(":material/logout:", key="gm_logout_btn", help="Logout")

    st.markdown('<hr style="margin-top: 10px;">', unsafe_allow_html=True)
    return logout_clicked
