import re

import streamlit as st
import streamlit.components.v1 as components

from utils.materials_api import (
    generate_subtopic_material,
    get_all_materials,
    list_subtopics,
    material_source_id,
)


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

    unit_code = material.get("unit_code", "")
    competency_name = material.get("competency_name", "")
    print("unit_code:", unit_code, "competency_name:", competency_name)

    # Subtopic generation sits ABOVE the slide viewer, not below it - this
    # is the thing a learner actually comes to this page to use, so it
    # shouldn't require scrolling past a 600px iframe first to find it.
    st.markdown(
        f"Selamat datang di materi unit **{unit_code or '-'}** - "
        f"**{competency_name or material.get('title', 'Untitled')}**. "
        f"Untuk mendapatkan materi, silahkan klik tombol **Lihat Daftar Subtopik**. "
        f"Silahkan klik tombol **Generate**, untuk mengenerate materi menggunakan LLM."
    )

    # Two-step, user-driven flow (not one automatic multi-call loop, which
    # would queue up behind itself on our single local Ollama instance and
    # take longer overall, not less): first list subtopics cheaply (titles
    # only), then the user clicks a SPECIFIC subtopic's own button to
    # generate just that one, in full depth, on demand.
    subtopics_key = f"material_subtopics_{material_id}"
    gen_disabled = not unit_code or unit_code == "-" or not competency_name
    if st.button("Lihat Daftar Subtopik", key="list_subtopics_btn", disabled=gen_disabled):
        with st.spinner("Menyusun daftar subtopik..."):
            sub_result = list_subtopics(unit_code, competency_name)
        if sub_result.get("success"):
            st.session_state[subtopics_key] = sub_result.get("subtopics", [])
        else:
            st.error(sub_result.get("error", "Gagal menyusun daftar subtopik."))

    subtopics = st.session_state.get(subtopics_key)
    if subtopics:
        st.markdown("### Subtopik")
        st.caption("Pilih subtopik yang ingin dipelajari lebih dulu - generate dilakukan satu per satu.")
        subtopic_results = st.session_state.setdefault("material_subtopic_results", {})
        for sub in subtopics:
            idx = sub.get("index")
            title = sub.get("title", f"Subtopik {idx + 1}")
            result_key = (material_id, idx)

            col_title, col_btn = st.columns([4, 1.3])
            with col_title:
                st.markdown(f"**{idx + 1}. {title}**")
            with col_btn:
                if st.button("Generate", key=f"gen_subtopic_{material_id}_{idx}", use_container_width=True):
                    with st.spinner(f"Menggenerate: {title}..."):
                        subtopic_results[result_key] = generate_subtopic_material(
                            unit_code, competency_name, idx, title
                        )

            sub_generated = subtopic_results.get(result_key)
            if sub_generated:
                if sub_generated.get("success"):
                    # Collapsible (st.expander) instead of dumping the
                    # material inline: a detailed subtopic can easily run
                    # several screens long, and without a way to roll it
                    # back up, generating subtopic 2 meant scrolling past
                    # all of subtopic 1's full text first. Starts expanded
                    # (right after generating, the learner wants to see
                    # it) - the expander's own header click is the
                    # "minimize" control from here on.
                    with st.expander(f"📄 {title}", expanded=True):
                        st.markdown(sub_generated.get("material", ""))
                        st.caption(f"Generated with {sub_generated.get('provider', 'the configured model')}")
                else:
                    st.error(sub_generated.get("error", "Gagal menggenerate subtopik ini."))
            st.divider()

    url = material.get("url", "")
    if url:
        st.markdown("### Materi Presentasi")
        components.iframe(_to_embed_url(url), height=600, scrolling=True)
        # st.link_button("Open in a new tab", url)
    else:
        st.info("This material does not have a viewable URL yet.")