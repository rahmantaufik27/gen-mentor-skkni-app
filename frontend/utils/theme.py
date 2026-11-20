"""
Shared design-system utility: one place that owns the color palette,
CSS injection, and the reusable header/sidebar/avatar snippets so every
page renders a consistent look instead of duplicating markup or CSS.
"""

import streamlit as st

# Brand palette - must stay in sync with the CSS variables in assets/css/main.css
# Direction: sarjana.jteti.ugm.ac.id (gold/navy/teal, Montserrat) - see the
# "GAMASKILL Redesign Study" artifact for the before/after this came from.
PRIMARY = "#0B1C2E"
SECONDARY = "#6B6F76"
ACCENT = "#FFC600"
SUCCESS = "#1C7A4D"
BACKGROUND = "#F6F6F3"
CARD = "#FFFFFF"
SOFT = "#EFEFEA"
TEXT = "#1C2127"
BORDER = "#E3E3DE"

BRAND_NAME = "GAMASKILL"
BRAND_TAGLINE = "Gateway for Adaptive Mastery and Advancement of Skills"

# Sidebar nav entries -> maps directly to st.session_state.current_page values
# consumed by pages/learner_profile.py
NAV_ITEMS = [
    {"key": "profile", "label": "My Profile", "icon": ":material/account_circle:"},
    {"key": "onboarding", "label": "Onboarding", "icon": ":material/rocket_launch:"},
    {"key": "data_analytics", "label": "Data Analytics", "icon": ":material/analytics:"},
    {"key": "engagement", "label": "Engagement", "icon": ":material/trending_up:"},
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


def confirm_exam_action(title: str, message: str, confirm_label: str, on_confirm):
    """Pop-up confirmation for an exam-ending action (Exit Exam / Submit
    All Answers). `on_confirm` runs only after the learner confirms; it
    returns None on success or an error message to show inside the dialog."""

    @st.dialog(title)
    def _dialog():
        st.write(message)
        cancel_col, confirm_col = st.columns(2)
        with cancel_col:
            if st.button("Cancel", use_container_width=True, key="gm_exam_confirm_cancel"):
                st.rerun()
        with confirm_col:
            if st.button(confirm_label, use_container_width=True, type="primary", key="gm_exam_confirm_ok"):
                error = on_confirm()
                if error:
                    st.error(error)
                else:
                    st.rerun()

    _dialog()


def _select_exam_question(view_state_key: str, index: int):
    st.session_state[view_state_key] = index


def render_exam_navigator(
    total_questions: int, status: dict, frontier: int, current: int, key_prefix: str, view_state_key: str
):
    """Right-hand, CLICKABLE "Question Navigator" status grid for the
    exam-fullscreen UI, shared by Practice (components/practice.py) and
    Test (pages/test.py) so both stay visually/behaviorally identical.

    `status` is {0-based index: "answered" | "skipped"}; `frontier` is the
    1-based furthest question number ever reached by forward (Submit/Skip)
    progression; `current` is the 1-based question on screen right now (it
    gets the gold ring). A cell is clickable only up to the frontier
    (jumping ahead to a never-opened question isn't allowed); clicking an
    answered or skipped cell reopens it so the learner can answer or
    change their answer (submit_answer upserts by index server-side).

    A click writes the 0-based index into st.session_state[view_state_key]
    through an on_click callback, which runs before the rerun - so jumping
    costs one script run, not a run plus an st.rerun().
    """

    # Exact class selectors (".st-key-x"), never substring ones
    # ('[class*="navbtn_1"]' also matches navbtn_10..19), and the class is
    # tripled so these outrank the app-wide
    # '.stButton button[kind^="secondary"]' !important rules in main.css.
    palette = {
        "answered": ("var(--success)", "#fff"),
        "skipped": ("var(--warning)", "#fff"),
        "unopened": ("var(--soft)", "var(--text-muted)"),
    }
    groups = {state: [] for state in palette}
    for i in range(1, total_questions + 1):
        item_status = status.get(i - 1)
        state = item_status if item_status in ("answered", "skipped") else "unopened"
        groups[state].append(f".st-key-{key_prefix}_navbtn_{i}" * 3)

    rules = []
    for state, (bg, fg) in palette.items():
        classes = groups[state]
        if not classes:
            continue
        buttons = ", ".join(f"{c} button" for c in classes)
        labels = ", ".join(f"{c} button {tag}" for c in classes for tag in ("p", "span", "div"))
        rules.append(
            f"{buttons} {{ background-color: {bg} !important; border: none !important; "
            f"color: {fg} !important; opacity: 1 !important; }}"
        )
        rules.append(f"{labels} {{ color: {fg} !important; }}")
    current_cls = f".st-key-{key_prefix}_navbtn_{current}" * 3
    rules.append(
        f"{current_cls} button {{ outline: 3px solid var(--accent) !important; outline-offset: 2px; }}"
    )
    st.markdown(f"<style>{' '.join(rules)}</style>", unsafe_allow_html=True)

    with st.container(key=f"{key_prefix}_gm_exam_navigator"):
        st.markdown('<div class="gm-exam-nav-title">Question Navigator</div>', unsafe_allow_html=True)

        for row_start in range(1, total_questions + 1, 6):
            row_numbers = range(row_start, min(row_start + 6, total_questions + 1))
            cols = st.columns(6)
            for col, i in zip(cols, row_numbers):
                with col:
                    st.button(
                        str(i), key=f"{key_prefix}_navbtn_{i}", disabled=(i > frontier),
                        use_container_width=True,
                        on_click=_select_exam_question, args=(view_state_key, i - 1),
                    )

        st.markdown(
            """
            <div class="gm-exam-legend">
                <div class="gm-exam-legend-row"><span class="gm-exam-legend-swatch answered"></span><b>Green</b>&nbsp;— answered</div>
                <div class="gm-exam-legend-row"><span class="gm-exam-legend-swatch skipped"></span><b>Orange</b>&nbsp;— skipped</div>
                <div class="gm-exam-legend-row"><span class="gm-exam-legend-swatch unopened"></span><b>Gray</b>&nbsp;— not opened</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


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
    """Render the brand lockup (logo mark + name + tagline) used in the sidebar and auth pages."""
    wrapper_class = "gm-auth-brand" if auth_style else "gm-brand"
    name_class = "gm-auth-brand-text" if auth_style else "gm-brand-text"
    tagline_class = "gm-auth-brand-tagline" if auth_style else "gm-brand-tagline"
    st.markdown(
        f"""
        <div class="{wrapper_class}">
            <div class="gm-brand-mark">🎓</div>
            <div class="gm-brand-text-wrap">
                <div class="{name_class}">{BRAND_NAME}</div>
                <div class="{tagline_class}">{BRAND_TAGLINE}</div>
            </div>
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
                _clear_material_detail_route()
                st.session_state.current_page = item["key"]
                st.rerun()

            entries = submenus.get(item["key"])
            if entries:
                with st.container(key=f"submenu_{item['key']}"):
                    for entry in entries:
                        _render_submenu_entry(item["key"], entry, active)


def _clear_material_detail_route():
    if "material_id" in st.query_params:
        del st.query_params["material_id"]


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
                    _clear_material_detail_route()
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
        _clear_material_detail_route()
        st.session_state.current_page = entry["key"]
        st.rerun()


def render_app_header(
    title: str, subtitle: str = "", user_name: str = "", user_email: str = "",
    user_photo_url: str = None, show_logout: bool = True,
) -> bool:
    """
    Render the top header: page title on the left, user chip + logout on the right.

    user_photo_url: the user's uploaded profile photo (see
    utils/profile_api.py::profile_photo_url), shown instead of the
    initials circle when given - pass None (the default) to always show
    initials, e.g. for a user who hasn't uploaded a photo.

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
            avatar_html = (
                f"<img class='gm-avatar gm-avatar-img' src='{user_photo_url}'>"
                if user_photo_url else
                f"<div class='gm-avatar'>{avatar_initials(user_name)}</div>"
            )
            chip_col, btn_col = st.columns([3, 1])
            with chip_col:
                st.markdown(
                    f"""
                    <div class="gm-user-chip" style="justify-content:flex-end;">
                        <div class="gm-user-meta" style="text-align:right;">
                            <div class="gm-user-name">{user_name}</div>
                            <div class="gm-user-role">{user_email}</div>
                        </div>
                        {avatar_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with btn_col:
                if show_logout:
                    logout_clicked = st.button(":material/logout:", key="gm_logout_btn", help="Logout")

    st.markdown('<hr style="margin-top: 10px;">', unsafe_allow_html=True)
    return logout_clicked
