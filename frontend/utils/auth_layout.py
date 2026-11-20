"""Shared pieces of the split-layout auth pages (pages/login.py, pages/register.py).

The CSS lives in assets/css/main.css under "Login page"; every rule there is
scoped by :has(.gm-login-brand), so any page that renders brand_panel() gets
the full layout.
"""

from html import escape

import streamlit as st

LOGO_SVG = (
    '<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true">'
    '<path d="M12 4 2 9l10 5 8-4v6h2V9L12 4Z" fill="#0B1C2E"/>'
    '<path d="M6 12.6V16c0 1.4 2.7 3 6 3s6-1.6 6-3v-3.4l-6 3-6-3Z" fill="#0B1C2E"/></svg>'
)

_ALERT_ICONS = {
    "error": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v6M12 16.5v.5"/></svg>',
    "warn": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/></svg>',
    "ok": '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="m5 12 4.5 4.5L19 7"/></svg>',
}


def hide_app_chrome():
    """Auth pages don't use the app shell: no sidebar, no Streamlit header."""
    st.markdown(
        """
        <style>
            [data-testid="collapsedControl"], [data-testid="baseButton-header-close"],
            ul[data-testid="stSidebarNavigation"], section[data-testid="stSidebar"],
            header[data-testid="stHeader"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _track(levels: int, met: bool) -> str:
    return "".join(
        f'<i class="gm-lb-seg{(" met" if met else " on") if i <= levels else ""}{" t" if i == 4 else ""}"></i>'
        for i in range(1, 7)
    )


def brand_panel(headline_html: str, lead: str):
    """Navy left panel. headline_html may contain one <em> for the gold phrase."""
    st.markdown(
        f"""<div class="gm-login-brand">
<div class="gm-lb-brand"><div class="gm-lb-logo">{LOGO_SVG}</div><div><div class="gm-lb-name">GAMASKILL</div><div class="gm-lb-tag">Gateway for Adaptive Mastery and Advancement of Skills</div></div></div>
<div class="gm-lb-pitch"><div class="gm-lb-h2">{headline_html}</div><div class="gm-lb-p">{escape(lead)}</div></div>
<div class="gm-lb-sample"><div class="gm-lb-k">Example · your level on each unit</div>
<div class="gm-lb-row"><div class="gm-lb-top"><div class="gm-lb-code">J.620100.010.01</div><div class="gm-lb-chip met">Target met</div></div><div class="gm-lb-track">{_track(4, True)}</div></div>
<div class="gm-lb-row"><div class="gm-lb-top"><div class="gm-lb-code">J.620100.017.02</div><div class="gm-lb-chip">2 levels to go</div></div><div class="gm-lb-track">{_track(2, False)}</div></div>
<div class="gm-lb-row"><div class="gm-lb-top"><div class="gm-lb-code">J.620100.005.02</div><div class="gm-lb-chip">3 levels to go</div></div><div class="gm-lb-track">{_track(1, False)}</div></div>
</div>
<div class="gm-lb-foot">&copy; DTETI UGM 2026</div>
</div>""",
        unsafe_allow_html=True,
    )


def form_top():
    """Small logo (shown only on narrow screens) and the "Back to home" link."""
    st.markdown(f'<div class="gm-login-mobile-brand"><div class="gm-lb-logo">{LOGO_SVG}</div>'
                '<div class="gm-lb-name dark">GAMASKILL</div></div>', unsafe_allow_html=True)
    st.markdown('<a class="gm-login-back" href="/landing" target="_self">← Back to home</a>', unsafe_allow_html=True)


def form_bottom():
    st.markdown('<div class="gm-login-admin">Administrator? '
                '<a href="/admin_login" target="_self">Sign in to the admin console</a></div>',
                unsafe_allow_html=True)


def heading(title: str, subtitle: str):
    st.markdown(f'<div class="gm-login-h1">{escape(title)}</div><div class="gm-login-sub">{escape(subtitle)}</div>',
                unsafe_allow_html=True)


def alert(kind: str, html_body: str):
    """kind: error | warn | ok. html_body is trusted HTML; escape user text first."""
    st.markdown(f'<div class="gm-login-alert {kind}">{_ALERT_ICONS[kind]}<div>{html_body}</div></div>',
                unsafe_allow_html=True)
