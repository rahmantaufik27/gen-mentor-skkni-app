import streamlit as st
from streamlit_option_menu import option_menu


def render_navigation():
    import time
    start = time.time()
    # st.write('<style>div.block-container{padding-top:2rem;}</style>', unsafe_allow_html=True)
    # pages = ["Onboarding", "Learning Path", "Learner Profile", "Dashboard"]
    pages = ["Quiz", "Learning Path", "Learner Profile"]
    icons = ["grid", "flag", "person"]
    page_to_mean_dict = {
        # "Onboarding": "Onboarding",
        "Quiz": "Quiz",
        "Learning Path": "Learning Path",
        "Learner Profile": "Learner Profile",
        # "Dashboard": "Dashboard",
    }
    with st.sidebar:
        # styles = {"container": {"padding": "0.2rem 0", "background-color": "#22222200"}}
        selected_menu_selection_name = option_menu(
            "",
            pages,
            default_index=pages.index(page_to_mean_dict[st.session_state.selected_page]),
            orientation="vertical",
            manual_select=pages.index(page_to_mean_dict[st.session_state.selected_page]),
            # styles=styles,
            icons=icons,
            menu_icon="cast",
            on_change=update_selected_page,
            key=f"menu_selection_name" # the key should be always the same as the key in the session state
        )
    # if selected_menu_selection_name != st.session_state.selected_page:
    #     st.session_state.selected_page = selected_menu_selection_name
    #     st.switch_page(f"pages/{selected_menu_selection_name.lower().replace(' ', '_')}.py")
    end = time.time()
    return selected_menu_selection_name


def update_selected_page(key):
    if st.session_state[key] != st.session_state.selected_page:
        # st.session_state["selected_page"] = st.session_state[key]
        # selected_menu_selection_name = st.session_state["selected_page"]
        # st.switch_page(f"pages/{selected_menu_selection_name.lower().replace(' ', '_')}.py")
        print("Switched to: ", st.session_state.selected_page)
