import re

import streamlit as st
import streamlit.components.v1 as components

from utils.materials_api import generate_learning_material, get_all_materials, material_source_id


def _to_embed_url(url: str) -> str:
    if not url:
        return url

    match = re.search(r"docs\.google\.com/(presentation|document|spreadsheets)/d/([^/]+)", url)
    if match:
        kind, file_id = match.group(1), match.group(2)
        return f"https://docs.google.com/{kind}/d/{file_id}/preview"

    match = re.search(r"drive\.google\.com/file/d/([^/]+)", url)
    if match:
        return f"https://drive.google.com/file/d/{match.group(1)}/preview"

    match = re.search(r"(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)", url)
    if match:
        return f"https://www.youtube.com/embed/{match.group(1)}"

    return url


def render_material_detail():
    if st.button("Back to Reading Materials", key="material_detail_back"):
        if "material_id" in st.query_params:
            del st.query_params["material_id"]
        st.session_state.current_page = "reading_materials"
        st.rerun()

    material_id = st.query_params.get("material_id", "")
    if not material_id:
        st.warning("No material was selected.")
        return

    with st.spinner("Loading material..."):
        result = get_all_materials()

    if not result.get("success"):
        st.error(f"Failed to load material: {result.get('error', 'Unknown error')}")
        return

    material = next(
        (item for item in result.get("materials", []) if material_source_id(item) == material_id),
        None,
    )
    if material is None:
        st.error("This material could not be found.")
        return

    material_type = str(material.get("type", "-")).title()
    st.subheader(material.get("title", "Untitled"))
    st.caption(f"Unit: {material.get('unit_code', '-')} · Type: {material_type}")

    url = material.get("url", "")
    if url:
        components.iframe(_to_embed_url(url), height=600, scrolling=True)
        # st.link_button("Open in a new tab", url)
    else:
        st.info("This material does not have a viewable URL yet.")

    unit_code = material.get("unit_code", "")
    competency_name = material.get("competency_name", "")
    if st.button(
        "Generate learning material",
        key="generate_learning_material",
        disabled=not unit_code or unit_code == "-" or not competency_name,
    ):
        with st.spinner("Generating learning material..."):
            result = generate_learning_material(unit_code, competency_name)
        st.session_state.setdefault("material_learning_results", {})[material_id] = result

    generated = st.session_state.get("material_learning_results", {}).get(material_id)
    if generated:
        if generated.get("success"):
            st.markdown("### Generated Learning Material")
            st.markdown(generated.get("material", ""))
            st.caption(f"Generated with {generated.get('provider', 'the configured model')}")
        else:
            st.error(generated.get("error", "Could not generate learning material."))