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

from utils.materials_api import get_all_materials, get_recommended_materials
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


def _type_icon(material_type: str) -> str:
    return TYPE_ICONS.get((material_type or "").lower(), "🔗")


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


def _material_source_id(material: dict) -> str:
    """Stable id for a material note. Materials have no DB id, so the URL is the
    most stable reference; fall back to title+unit when there's no URL."""
    return material.get("url") or f"{material.get('title', '')}|{material.get('unit_code', '')}"


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


def _render_material_list(materials: list, key_prefix: str, show_status: bool, saved_ids: set):
    """Render one card per material with a View button that opens the inline
    viewer and a Save-to-Notes toggle."""
    for idx, material in enumerate(materials):
        with st.container(border=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                icon = _type_icon(material.get("type"))
                st.markdown(f"**{icon} {material.get('title', 'Untitled')}**")

                meta = f"Unit: {material.get('unit_code', '-')} · Type: {str(material.get('type', '-')).title()}"
                if show_status:
                    status = material.get("mastery_status", "Remedial")
                    badge_class = "gm-badge-success" if status == "Mastered" else "gm-badge-danger"
                    st.markdown(
                        f"<span class='gm-badge {badge_class}'>{status}</span> "
                        f"<span style='color: var(--text-muted); font-size: 13px;'>"
                        f"{meta} · Target: {material.get('target_level', '-')}</span>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.caption(meta)
            with col2:
                if st.button("Open Material", type="primary", key=f"view_{key_prefix}_{idx}", use_container_width=True):
                    # Fire-and-forget: count this material open for Learning Path
                    # stats. Never blocks or breaks the viewer if it fails.
                    record_material_view(material.get("unit_code"))
                    # Open the material in a modal dialog so it's immediately
                    # visible in the viewport (rather than below the fold).
                    _material_dialog(material)

                fields = _material_note_fields(material)
                render_save_button(
                    SOURCE_MATERIAL, _material_source_id(material),
                    fields["snapshot_text"], title=fields["title"], source_ref=fields["source_ref"],
                    saved_ids=saved_ids, key=f"note_{key_prefix}_{idx}",
                )


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
                _render_material_list(materials, key_prefix="rec", show_status=True, saved_ids=saved_ids)

    with tab_all:
        result = get_all_materials()
        if not result.get("success"):
            st.error(f"Failed to load materials: {result.get('error', 'Unknown error')}")
        else:
            materials = result.get("materials", [])
            if not materials:
                st.info("No materials available yet.")
            else:
                _render_material_list(materials, key_prefix="all", show_status=False, saved_ids=saved_ids)
