"""
Public landing page - the first thing a signed-out visitor sees (main.py
sends them here; Sign In / Create Account lead on to pages/login.py and
pages/register.py).

The page itself is assets/landing.html, shown in an iframe so its own
script can run (the clickable career ladder) - st.markdown would strip it.
The frame resizes itself to its content, so the browser page scrolls
normally and the frame never shows its own scrollbar.
"""

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="GAMASKILL", page_icon=":books:", layout="wide", initial_sidebar_state="collapsed")

# A signed-in learner has no use for the landing page.
if st.session_state.get("logged_in"):
    st.switch_page("main.py")

# Full-bleed: no Streamlit header, sidebar, or page padding around the frame.
st.markdown(
    """
    <style>
        [data-testid="collapsedControl"], [data-testid="stSidebar"], header[data-testid="stHeader"] { display: none !important; }
        .block-container, [data-testid="stMainBlockContainer"] { padding: 0 !important; max-width: 100% !important; }
        [data-testid="stAppViewContainer"], .stApp { background: #F6F6F3; }
        iframe { display: block; width: 100%; border: none; }
        /* This <style> block is itself a page element; without these two
           rules it leaves a strip of blank space above the frame. */
        [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] { gap: 0 !important; }
        [data-testid="stElementContainer"]:has(style) { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

with open("assets/landing.html", "r", encoding="utf-8") as f:
    components.html(f.read(), height=3200, scrolling=False)
