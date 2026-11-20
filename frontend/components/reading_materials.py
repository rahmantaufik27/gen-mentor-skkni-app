"""
Reading Materials learning method.

Self-contained module: exposes render_reading_materials() as its only public
entry point, so components/learning_path.py (and any future learning method)
can use it without knowing anything about materials.json, the recommendation
logic, or the inline-viewer mechanics.
"""

from datetime import datetime
from html import escape

import streamlit as st

from data.unit_names_en import UNIT_NAMES_EN
from utils.materials_api import get_all_materials, get_all_units, get_recommended_materials, material_source_id
from utils.practice_api import record_material_view, get_read_material_ids
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


def _unit_titles() -> dict:
    """Unit code -> unit name, for cards whose material record has no name
    (the recommendation feed doesn't carry one). Cached by get_all_units."""
    result = get_all_units()
    return {u.get("unit_code"): u.get("title") or "" for u in result.get("units", [])}


def datetime_now_iso() -> str:
    return datetime.now().isoformat()


def _type_icon(material_type: str) -> str:
    return TYPE_ICONS.get((material_type or "").lower(), "🔗")


def _type_accent_kind(material_type: str) -> str:
    return TYPE_ACCENT_KIND.get((material_type or "").lower(), "neutral")


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


def _read_date(iso) -> str:
    try:
        from datetime import datetime
        return datetime.fromisoformat(iso).strftime("%d %b").lstrip("0")
    except (TypeError, ValueError):
        return ""


def _render_material_card(material: dict, key_prefix: str, idx: int, show_status: bool, saved_ids: set, read_ids: dict):
    """Render a single material as a card: icon, title, meta chips, then the
    View/Save actions - the unit of the grid built by _render_material_list.

    is_read marks a card the learner has opened before (stored on the
    server, see render_reading_materials) - it gets a distinct "read" key so
    the scoped CSS in main.css can style it, its own chip so the state isn't
    color-only, and an "Open again" label on its main button."""
    source_id = material_source_id(material)
    is_read = source_id in read_ids
    card_kind = "read" if is_read else "unread"
    unit_code = str(material.get("unit_code") or "-")
    unit_name = material.get("competency_name") or _unit_titles().get(unit_code, "")

    # Option A ("quiet card", see the Material Card Options mockup): the card
    # stays white in both states. Read shows as a green check on the icon, a
    # "Read on <date>" note, and a green "Open again" button; Save and
    # Discuss are icon buttons so the main action stands out.
    with st.container(border=True, key=f"gm_material_card_{card_kind}_{key_prefix}_{idx}"):
        check = "<div class='gm-mc-check'>✓</div>" if is_read else ""
        st.markdown(
            f"<div class='gm-mc-top'><div class='gm-mc-thumb'>{_type_icon(material.get('type'))}{check}</div>"
            f"<div class='gm-mc-head'><div class='gm-mc-title'>{escape(str(material.get('title', 'Untitled')))}</div>"
            f"<div class='gm-mc-unit'>{escape(unit_code)}</div>"
            + (f"<div class='gm-mc-unitname'>{escape(unit_name)}</div>" if unit_name else "")
            + (f"<div class='gm-mc-unitname-en'>{escape(UNIT_NAMES_EN[unit_code])}</div>" if unit_code in UNIT_NAMES_EN else "")
            + "</div></div>",
            unsafe_allow_html=True,
        )

        parts = []
        if show_status:
            status = material.get("mastery_status", "Remedial")
            kind = "ok" if status == "Mastered" else "gap"
            parts.append(f"<div class='gm-mc-dot {kind}'></div><div class='gm-mc-status {kind}'>{escape(status)}</div>"
                         f"<div>· target {escape(str(material.get('target_level', '-')))}</div>")
        if is_read:
            when = _read_date(read_ids.get(source_id))
            parts.append(f"<div>{'·' if show_status else ''}</div><div class='gm-mc-read'>✓ Read{' on ' + when if when else ''}</div>")
        if parts:
            st.markdown(f"<div class='gm-mc-line'>{''.join(parts)}</div>", unsafe_allow_html=True)

        open_col, save_col, discuss_col = st.columns([5, 1.1, 1.1], gap="small")
        with open_col:
            label = ":material/replay: Open again" if is_read else "Open material :material/arrow_forward:"
            if st.button(label, type="primary", key=f"view_{key_prefix}_{idx}", use_container_width=True):
                # Fire-and-forget: stores which material was opened, which
                # both feeds Learning Path stats and keeps the "Read" mark
                # after logout. Never blocks the viewer if it fails.
                record_material_view(material.get("unit_code"), source_id)
                read_ids.setdefault(source_id, datetime_now_iso())
                st.query_params["material_id"] = source_id
                st.session_state.current_page = "material_detail"
                st.rerun()
        with save_col:
            fields = _material_note_fields(material)
            render_save_button(
                SOURCE_MATERIAL, source_id,
                fields["snapshot_text"], title=fields["title"], source_ref=fields["source_ref"],
                saved_ids=saved_ids, key=f"note_{key_prefix}_{idx}", use_container_width=True, material_icon=True,
            )
        with discuss_col:
            if st.button(":material/forum:", key=f"discuss_{key_prefix}_{idx}", use_container_width=True,
                         help="Discuss this material"):
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


def render_reading_materials():
    """Render the Reading Materials learning method: recommended + all materials, with an inline viewer."""
    # Which materials the user has already saved to Notes - fetched once per
    # render so each card's Save/Remove toggle shows the right state without a
    # per-button lookup.
    saved_ids = get_saved_source_ids(SOURCE_MATERIAL)
    # Which materials this learner has opened before. Loaded from the server
    # once per login (each opened material is recorded with its id), so the
    # "Read" mark survives logout; materials opened during this session are
    # added to the same set as they're opened.
    if (st.session_state.get("gm_materials_read_user") != st.session_state.get("userId")
            or not isinstance(st.session_state.get("gm_materials_read"), dict)):
        st.session_state.gm_materials_read = get_read_material_ids()
        st.session_state.gm_materials_read_user = st.session_state.get("userId")
    read_ids = st.session_state.gm_materials_read

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
