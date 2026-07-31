import streamlit as st
from utils.state import initialize_session_state, save_persistent_state, load_persistent_state

# ============================================================================
# INITIALIZE SESSION STATE
# ============================================================================
initialize_session_state()

# ============================================================================
# PAGE CONFIG - Called only once, with all settings
# ============================================================================
st.set_page_config(
    page_title="GenQ-SKKNI",
    page_icon=":books:",
    layout="wide",
    initial_sidebar_state="collapsed"  # Hide default Streamlit sidebar
)
st.set_option("client.showSidebarNavigation", False)

# ============================================================================
# HIDE STREAMLIT'S AUTOMATIC PAGE SIDEBAR (with CSS)
# ============================================================================
# hide_sidebar = """
# <style>
#     /* Hide the automatic page sidebar completely */
#     [data-testid="collapsedControl"] {
#         display: none !important;
#     }
#     [data-testid="baseButton-header-close"] {
#         display: none !important;
#     }
#     ul[data-testid="stSidebarNavigation"] {
#         display: none !important;
#     }
#     /* Hide the sidebar entirely */
#     section[data-testid="stSidebar"] {
#         display: none !important;
#     }
# </style>
# """
# st.markdown(hide_sidebar, unsafe_allow_html=True)

# ============================================================================
# LOAD ASSETS & CSS (with error handling)
# ============================================================================
# try:
#     st.logo("./assets/avatar.png")
# except Exception as e:
#     pass

try:
    with open('./assets/css/main.css', 'r') as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except Exception as e:
    pass

# ============================================================================
# AUTHENTICATION CHECK - CONDITIONAL NAVIGATION
# ============================================================================
is_logged_in = st.session_state.get("logged_in", False)

if is_logged_in:
    # ========================================================================
    # AUTHENTICATED - SHOW LEARNER PROFILE AS MAIN HUB
    # (learner_profile.py handles all navigation)
    # ========================================================================
    
    # Auto-save state
    st.session_state.setdefault("_autosave_enabled", True)
    try:
        save_persistent_state()
    except Exception:
        pass

    # Load the learner profile page as main hub
    exec(open("pages/learner_profile.py", encoding="utf-8").read())

else:
    # ========================================================================
    # NOT AUTHENTICATED - SHOW LOGIN PAGE
    # ========================================================================
    st.switch_page("pages/login.py")
