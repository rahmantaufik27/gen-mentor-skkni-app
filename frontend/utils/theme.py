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

BRAND_NAME = "GenMentor-SKKNI"

# Sidebar nav entries -> maps directly to st.session_state.current_page values
# consumed by pages/learner_profile.py
NAV_ITEMS = [
    {"key": "profile", "label": "My Profile", "icon": ":material/account_circle:"},
    {"key": "learning_path", "label": "Learning Path", "icon": ":material/school:"},
    {"key": "test", "label": "Test", "icon": ":material/assignment:"},
]
# Admin is a separate module (pages/admin_login.py + pages/admin_dashboard.py,
# its own login and session-state flag) - deliberately not part of the
# learner sidebar. See components/admin_shell.py.


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


def render_sidebar_nav(active: str, submenus: dict = None):
    """
    Render the left navigation sidebar (brand + nav items), with optional
    nested submenu items shown indented under a NAV_ITEMS entry - e.g.
    Learning Path's Reading Materials / Learning with Chatbot Assistance /
    Practice with Generative Questions / Notes / Reflection Learning items.

    Each submenu entry is either:
      - a direct nav item {"key":..., "label":...} - clicking it navigates
        straight to that page, exactly like a top-level item; or
      - a nested group {"label":..., "children": [{"key":..., "label":...}, ...]}
        (e.g. Learning Path's "Notes" group, containing Cue Questions and
        Key Points) - rendered as an expandable/dropdown submenu
        (st.expander) that reveals its children's nav buttons when opened;
        auto-expanded whenever `active` is one of its children so the
        current page's group is never hidden.

    Submenu items are always visible (not gated by their parent being
    active) and every leaf is a full page in its own right, so `active`
    alone (checked against NAV_ITEMS, submenu, and group-child keys)
    determines every highlight. Every item stays clickable at all times -
    Test/Practice eligibility (see utils/gating.py) is enforced by each
    page disabling its own Start button instead, never by hiding or
    disabling the menu.

    Args:
        active: current page key (st.session_state.current_page)
        submenus: {item_key: [entry, ...]} - optional. Any NAV_ITEMS entry
            with a matching key gets these entries rendered underneath it,
            always visible, generic enough for any future nav item to gain
            a submenu (nested or flat) the same way.
    """
    submenus = submenus or {}

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

            entries = submenus.get(item["key"])
            if entries:
                with st.container(key=f"submenu_{item['key']}"):
                    for entry in entries:
                        _render_submenu_entry(item["key"], entry, active)


def _render_submenu_entry(parent_key: str, entry: dict, active: str):
    """
    Render one Learning-Path-style submenu entry under `parent_key`: either
    a direct nav button ({"key", "label"}) or, if it has "children", a
    dropdown group (st.expander) of nav buttons - see render_sidebar_nav.
    """
    children = entry.get("children")
    if children:
        group_is_active = any(active == child["key"] for child in children)
        with st.expander(entry["label"], expanded=group_is_active):
            for child in children:
                child_is_active = active == child["key"]
                if st.button(
                    child["label"],
                    use_container_width=True,
                    type="primary" if child_is_active else "secondary",
                    key=f"nav_grandchild_{parent_key}_{child['key']}",
                ):
                    st.session_state.current_page = child["key"]
                    st.rerun()
        return

    entry_is_active = active == entry["key"]
    if st.button(
        entry["label"],
        use_container_width=True,
        type="primary" if entry_is_active else "secondary",
        key=f"nav_child_{parent_key}_{entry['key']}",
    ):
        st.session_state.current_page = entry["key"]
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
