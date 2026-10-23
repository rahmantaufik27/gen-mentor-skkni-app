"""
App entry point (`streamlit run main.py`).

Acts as the router: unauthenticated users are sent to the Login page;
authenticated users get pages/learner_profile.py exec'd in place as the
main hub (which in turn exec's pages/test.py for the Test tab). This is
also the only place that calls st.set_page_config()/inject_theme() for the
authenticated shell - Login/Register are separate entry scripts with their
own config.
"""

import streamlit as st
from utils.state import initialize_session_state
from utils.theme import inject_theme

# ============================================================================
# INITIALIZE SESSION STATE
# ============================================================================
initialize_session_state()

# ============================================================================
# PAGE CONFIG - Called only once, with all settings
# ============================================================================
st.set_page_config(
    page_title="GAMASKILL",
    page_icon=":books:",
    layout="wide",
    initial_sidebar_state="expanded"  # Real left nav sidebar (custom content, not Streamlit's auto page list)
)
st.set_option("client.showSidebarNavigation", False)

# ============================================================================
# LOAD SHARED THEME (palette, typography, cards, buttons, sidebar, header)
# ============================================================================
inject_theme()

# ============================================================================
# AUTHENTICATION CHECK - CONDITIONAL NAVIGATION
# ============================================================================
is_logged_in = st.session_state.get("logged_in", False)

if is_logged_in:
    # ========================================================================
    # AUTHENTICATED - ONBOARDING (first login only) OR LEARNER PROFILE HUB
    # (learner_profile.py handles all navigation). onboarding_completed comes
    # from the backend at login (see pages/login.py) - defaults to True so a
    # session missing it (e.g. an older login flow) never gets trapped in
    # onboarding unexpectedly.
    # ========================================================================
    if not st.session_state.get("onboarding_completed", True):
        exec(open("pages/onboarding.py", encoding="utf-8").read())
    else:
        # Load the learner profile page as main hub
        exec(open("pages/learner_profile.py", encoding="utf-8").read())

else:
    # ========================================================================
    # NOT AUTHENTICATED - SHOW LOGIN PAGE
    # ========================================================================
    st.switch_page("pages/login.py")
