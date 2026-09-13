"""
Reading Materials learning method.

Self-contained module: exposes render_reading_materials() as its only public
entry point, so components/learning_path.py (and any future learning method)
can use it without knowing anything about materials.json, the recommendation
logic, or the inline-viewer mechanics.
"""

import re

import streamlit as st
import streamlit.components.v1 as components

from utils.materials_api import get_all_materials, get_recommended_materials, material_source_id
from utils.practice_api import record_material_view
from utils.notes_api import get_saved_source_ids, SOURCE_MATERIAL
from components.notes import render_save_button

TYPE_ICONS = {
    "presentation": "📄",
    "pdf": "📄",
    "document": "📄",
    "video": "🎬",
    "article": "📰",
}

# Content-type color coding (icon + type chip) - a small, calm "edtech" set
# (blue/teal/violet) kept apart from the app's red/green brand colors, which
# stay reserved for actions and mastery/progress states. See the "Material
# cards" section of assets/css/main.css for the actual gm-accent-*/gm-badge-*
# color values.
TYPE_ACCENT_KIND = {
    "presentation": "blue",
    "pdf": "blue",
    "document": "blue",
    "video": "violet",
    "article": "teal",
}


def _type_icon(material_type: str) -> str:
    return TYPE_ICONS.get((material_type or "").lower(), "🔗")


def _type_accent_kind(material_type: str) -> str:
    return TYPE_ACCENT_KIND.get((material_type or "").lower(), "neutral")


def _to_embed_url(url: str) -> str:
    """
    Convert a share URL into an embeddable "preview" URL so the material can
    be viewed inline without downloading it first. Falls back to the original
    URL when no known provider pattern matches (many public pages still embed
    fine as-is).
    """
    if not url:
        return url

    # Google Slides / Docs / Sheets: .../d/<ID>/edit... -> .../d/<ID>/preview
    match = re.search(r"docs\.google\.com/(presentation|document|spreadsheets)/d/([^/]+)", url)
    if match:
        kind, file_id = match.group(1), match.group(2)
        return f"https://docs.google.com/{kind}/d/{file_id}/preview"

    # Google Drive file: .../file/d/<ID>/... -> .../file/d/<ID>/preview
    match = re.search(r"drive\.google\.com/file/d/([^/]+)", url)
    if match:
        return f"https://drive.google.com/file/d/{match.group(1)}/preview"

    # YouTube: watch?v=<ID> or youtu.be/<ID> -> /embed/<ID>
    match = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)", url)
    if match:
        return f"https://www.youtube.com/embed/{match.group(1)}"

    # Direct PDF / unknown provider: most browsers render these natively in an iframe
    return url


def _material_note_fields(material: dict) -> dict:
    """Build the note payload (snapshot_text + source_ref) for a material so it
    stays understandable and can be reopened later."""
    unit = material.get("unit_code", "-")
    mtype = str(material.get("type", "-")).title()
    snapshot = f"{material.get('title', 'Untitled')}  (Unit {unit} · {mtype})"
    source_ref = {
        "title": material.get("title"),
        "type": material.get("type"),
        "url": material.get("url"),
        "unit_code": material.get("unit_code"),
    }
    return {"snapshot_text": snapshot, "title": material.get("title"), "source_ref": source_ref}


# Cards per row in the materials grid. 2 (rather than a tighter 3) gives
# each card enough width that its icon/title/chips/buttons have breathing
# room instead of crowding the card's border.
_GRID_COLS = 2


def _render_material_list(materials: list, key_prefix: str, show_status: bool, saved_ids: set, read_ids: set):
    """Render materials as a card grid (_GRID_COLS per row) rather than a
    single stacked list - each card has a type icon, a clamped title, meta
    chips, and its View/Save actions."""
    for row_start in range(0, len(materials), _GRID_COLS):
        row = materials[row_start:row_start + _GRID_COLS]
        for col, offset in zip(st.columns(_GRID_COLS, gap="medium"), range(len(row))):
            with col:
                _render_material_card(row[offset], key_prefix, row_start + offset, show_status, saved_ids, read_ids)


def _render_material_card(material: dict, key_prefix: str, idx: int, show_status: bool, saved_ids: set, read_ids: set):
    """Render a single material as a card: icon, title, meta chips, then the
    View/Save actions - the unit of the grid built by _render_material_list.

    is_read marks a card that was opened earlier this session (see
    render_reading_materials) - it gets a distinct "read" key so the scoped
    CSS in main.css can tint it and its own chip so the state isn't
    color-only."""
    source_id = material_source_id(material)
    is_read = source_id in read_ids
    card_kind = "read" if is_read else "unread"
    accent = _type_accent_kind(material.get("type"))

    with st.container(border=True, key=f"gm_material_card_{card_kind}_{key_prefix}_{idx}"):
        icon = _type_icon(material.get("type"))
        st.markdown(f"<div class='gm-material-icon gm-accent-{accent}'>{icon}</div>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='gm-material-title'>{material.get('title', 'Untitled')}</div>",
            unsafe_allow_html=True,
        )

        # Color story: blue/teal/violet identify content type; green marks
        # progress (Mastered unit, or a material already Read); amber flags
        # a unit that still needs work - a nudge, not an alarm-red "danger".
        chips = [
            f"<span class='gm-badge gm-badge-neutral'>Unit {material.get('unit_code', '-')}</span>",
            f"<span class='gm-badge gm-badge-{accent}'>{str(material.get('type', '-')).title()}</span>",
        ]
        if show_status:
            status = material.get("mastery_status", "Remedial")
            badge_class = "gm-badge-success" if status == "Mastered" else "gm-badge-amber"
            chips.append(f"<span class='gm-badge {badge_class}'>{status}</span>")
        if is_read:
            chips.append("<span class='gm-badge gm-badge-read'>✓ Read</span>")
        st.markdown(f"<div class='gm-material-meta'>{''.join(chips)}</div>", unsafe_allow_html=True)
        if show_status:
            st.caption(f"Target: {material.get('target_level', '-')}")

        # Three compact buttons side-by-side - see main.css's
        # "Compact Open Material / Save-to-Notes buttons" rule, which
        # already shrinks padding/font for buttons in this card.
        open_col, save_col, discuss_col = st.columns(3)
        with open_col:
            if st.button("Open Material", type="primary", key=f"view_{key_prefix}_{idx}", use_container_width=True):
                # Fire-and-forget: count this material open for Learning Path
                # stats. Never blocks or breaks the viewer if it fails.
                record_material_view(material.get("unit_code"))
                # Mark it read for the rest of this session so the card
                # tints green on the next rerun (opening the dialog below
                # triggers one).
                read_ids.add(source_id)
                # Open the material in a modal dialog so it's immediately
                # visible in the viewport (rather than below the fold).
                _material_dialog(material)
        with save_col:
            fields = _material_note_fields(material)
            render_save_button(
                SOURCE_MATERIAL, source_id,
                fields["snapshot_text"], title=fields["title"], source_ref=fields["source_ref"],
                saved_ids=saved_ids, key=f"note_{key_prefix}_{idx}", use_container_width=True,
            )
        with discuss_col:
            if st.button("💬 Discuss", key=f"discuss_{key_prefix}_{idx}", use_container_width=True):
                # Hand off to the Discussion page (Learning Path -> Discussion),
                # pre-selecting this material's unit + thread - see
                # components/discussion.py's prefill handling.
                st.session_state["discussion_prefill_unit"] = material.get("unit_code")
                st.session_state["discussion_prefill_material_id"] = source_id
                st.session_state["discussion_prefill_material_title"] = material.get("title")
                # Bumped so Discussion's selectors always remount fresh for a
                # NEW deep-link, even if the user had already changed them
                # earlier in this session (a Streamlit widget only honors
                # its `index=` on first mount for a given key otherwise).
                st.session_state["discussion_prefill_nonce"] = st.session_state.get("discussion_prefill_nonce", 0) + 1
                st.session_state.current_page = "discussion"
                st.rerun()


@st.dialog("Reading Material", width="large")
def _material_dialog(material: dict):
    """Show the selected material inside a modal dialog so its content is
    immediately visible in the viewport (centered overlay), instead of an
    inline viewer that could sit below the fold. Dismiss via the dialog's
    built-in close control."""
    st.markdown(f"#### {_type_icon(material.get('type'))} {material.get('title', 'Untitled')}")
    st.caption(
        f"Unit: {material.get('unit_code', '-')} · Type: {str(material.get('type', '-')).title()}"
    )

    embed_url = _to_embed_url(material.get("url", ""))
    components.iframe(embed_url, height=600, scrolling=True)
    st.caption(f"Having trouble viewing it here? [Open in a new tab ↗]({material.get('url', '')})")


def render_reading_materials():
    """Render the Reading Materials learning method: recommended + all materials, with an inline viewer."""
    # Which materials the user has already saved to Notes - fetched once per
    # render so each card's Save/Remove toggle shows the right state without a
    # per-button lookup.
    saved_ids = get_saved_source_ids(SOURCE_MATERIAL)
    # Which materials have been opened this session, so their cards can be
    # tinted lime green. Materials have no DB id (see utils/materials_api.py::material_source_id)
    # and per-material view history isn't tracked server-side (the backend
    # only aggregates view counts per unit_code), so this is session-only -
    # it resets on a fresh login/reload rather than persisting long-term.
    read_ids = st.session_state.setdefault("gm_materials_read", set())

    tab_recommended, tab_all = st.tabs(["🎯 Recommended for You", "📚 All Materials"])

    with tab_recommended:
        result = get_recommended_materials()
        if not result.get("success"):
            st.error(f"Failed to load recommended materials: {result.get('error', 'Unknown error')}")
        elif result.get("all_mastered"):
            st.success("🎉 All units are currently Mastered! Check out All Materials to keep learning.")
        else:
            materials = result.get("materials", [])
            if not materials:
                st.info("No recommended materials found for your current gaps yet.")
            else:
                _render_material_list(materials, key_prefix="rec", show_status=True, saved_ids=saved_ids, read_ids=read_ids)

    with tab_all:
        result = get_all_materials()
        if not result.get("success"):
            st.error(f"Failed to load materials: {result.get('error', 'Unknown error')}")
        else:
            materials = result.get("materials", [])
            if not materials:
                st.info("No materials available yet.")
            else:
                _render_material_list(materials, key_prefix="all", show_status=False, saved_ids=saved_ids, read_ids=read_ids)
