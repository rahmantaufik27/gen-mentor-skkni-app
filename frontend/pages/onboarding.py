"""
Onboarding wizard - shown once right after a first login (see main.py,
which exec's this instead of pages/learner_profile.py while
st.session_state.onboarding_completed is False).

Five steps, driven entirely by st.session_state.onboarding_step (1-5):
  1. Welcome           - what GAMASKILL is, grounded in the SKKNI standard
  2. Choose Your Path   - pick a target SKKNI level/role, preview the ladder
  3. Your Journey       - the 6 real units under today's active track
  4. Building Your Path - a short animated payoff for steps 2-3
  5. Ready               - recap + hand-off into the learner hub

Every "Skip" (steps 1-2) and both buttons on step 5 call
utils/onboarding_api.py::complete_onboarding() and hand off into the normal
learner hub (pages/learner_profile.py, via main.py) - skipping always lands
on Profile Overview, same as finishing normally with no goal chosen.

NOTE: main.py handles authentication check, st.set_page_config(), and theme
injection - this code is exec'd by main.py, so don't duplicate those calls.
"""

import streamlit as st
import streamlit.components.v1 as components

from utils.theme import render_brand
from utils.onboarding_api import complete_onboarding
from utils.materials_api import get_all_units
from data.skkni_ladder import (
    LEVELS, LEVEL_ICONS, LEVEL_COLORS, ACTIVE_LEVEL, ACTIVE_ROLE, get_roles_for_level,
)

TOTAL_STEPS = 5

# Onboarding is a focused, full-bleed wizard - not part of the normal app
# shell (utils/theme.py::render_sidebar_nav) - hide the sidebar the same way
# pages/login.py does for the auth pages.
st.markdown(
    """
    <style>
        [data-testid="collapsedControl"] { display: none !important; }
        section[data-testid="stSidebar"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

if "onboarding_step" not in st.session_state:
    st.session_state.onboarding_step = 1
if "onboarding_target_level" not in st.session_state:
    st.session_state.onboarding_target_level = None
if "onboarding_target_role" not in st.session_state:
    st.session_state.onboarding_target_role = None


def _dots(on: int):
    dots_html = "".join(
        f'<i class="{"on" if i <= on else ""}"></i>' for i in range(1, TOTAL_STEPS + 1)
    )
    st.markdown(f'<div class="gm-onb-dots">{dots_html}</div>', unsafe_allow_html=True)


def _finish_onboarding(next_page: str, target_role: str = None, target_level: int = None):
    """Persist onboarding completion, then hand off into the learner hub."""
    complete_onboarding(target_role, target_level)
    st.session_state.onboarding_completed = True
    st.session_state.current_page = next_page
    for key in ("onboarding_step", "onboarding_target_level", "onboarding_target_role"):
        st.session_state.pop(key, None)
    st.rerun()


def _render_step_welcome():
    first_name = (st.session_state.get("user_name") or "there").split(" ")[0]
    _dots(1)
    st.markdown(
        """
        <div class="gm-onb-pill-row">
            <span class="gm-onb-pill">SKKNI · Kepmenaker 282/2016</span>
            <span class="gm-onb-pill">BNSP-regulated</span>
            <span class="gm-onb-pill">PON TIK 2025</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f"### Welcome, {first_name}! 👋")
    st.write(
        "GAMASKILL is an adaptive mastery platform, built on Indonesia's official "
        "SKKNI competency standard. Instead of a fixed syllabus, it tracks what you "
        "actually know, closes the gaps, and moves you forward one competency at a "
        "time — toward a real, nationally recognized career ladder."
    )
    st.write("")
    if st.button("Continue", type="primary", use_container_width=True, key="onb_w_continue"):
        st.session_state.onboarding_step = 2
        st.rerun()
    if st.button("Skip intro", use_container_width=True, key="onb_w_skip"):
        _finish_onboarding("profile")


def _render_step_path():
    _dots(2)
    st.markdown("### Where do you want to go?")
    st.write(
        f"Pick a level to preview the roles there. Wherever you aim, your ladder "
        f"always starts at the one track open today — **{ACTIVE_ROLE}**."
    )

    default_level = st.session_state.onboarding_target_level or (ACTIVE_LEVEL + 1)
    cols = st.columns(len(LEVELS))
    for col, level in zip(cols, LEVELS):
        with col:
            is_selected = st.session_state.get("onb_selected_level", default_level) == level
            if st.button(
                f"L{level}", key=f"onb_lvl_{level}",
                type="primary" if is_selected else "secondary",
                use_container_width=True,
            ):
                st.session_state.onb_selected_level = level
                st.rerun()

    selected_level = st.session_state.get("onb_selected_level", default_level)
    roles = get_roles_for_level(selected_level)
    selected_role = st.radio(
        "Roles at this level", roles, key=f"onb_role_radio_{selected_level}",
        label_visibility="collapsed",
    )

    _render_ladder_preview(selected_level, selected_role)

    st.write("")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("← Back", use_container_width=True, key="onb_p_back"):
            st.session_state.onboarding_step = 1
            st.rerun()
    with c2:
        if st.button("Set as my goal", type="primary", use_container_width=True, key="onb_p_continue"):
            st.session_state.onboarding_target_level = selected_level
            st.session_state.onboarding_target_role = selected_role
            st.session_state.onboarding_step = 3
            st.rerun()
    if st.button("Skip — decide later", use_container_width=True, key="onb_p_skip"):
        _finish_onboarding("profile")


def _render_ladder_preview(goal_level: int, goal_role: str):
    """The rising-staircase career ladder (levels 2-9), goal level ringed in
    gold, every level but ACTIVE_LEVEL tagged as a locked preview."""
    chips = []
    for i, level in enumerate(LEVELS):
        roles_here = get_roles_for_level(level)
        role_label = goal_role if level == goal_level and goal_role in roles_here else roles_here[0]
        classes = ["gm-onb-lchip"]
        if level == ACTIVE_LEVEL:
            tagline = '<span class="gm-onb-tagline now">✓ available now</span>'
        elif level == goal_level:
            classes.append("goal")
            tagline = '<span class="gm-onb-tagline">🎯 your goal</span>'
        else:
            classes.append("dim")
            tagline = '<span class="gm-onb-tagline">🔒 coming soon</span>'
            if level == LEVELS[-1]:
                tagline = '<span class="gm-onb-tagline">SKKNI top level</span>'

        crown = '<span class="gm-onb-crown">👑</span>' if level == LEVELS[-1] else ""
        arrow = '<span class="gm-onb-arrow-r">→</span>' if level != LEVELS[-1] else ""
        offset = -7 * i
        # Built as ONE unbroken line (no blank lines mid-block) - Streamlit's
        # markdown renderer only treats a run of HTML as raw markup for as
        # long as it sees no blank line; a blank line (e.g. from an empty
        # `crown`/`arrow` placeholder sitting alone on its own source line)
        # silently ends the HTML block early and the rest renders as escaped
        # text instead of markup.
        chips.append(
            f'<div class="{" ".join(classes)}" style="transform:translateY({offset}px)">'
            f'{crown}'
            f'<div class="gm-onb-lv-badge">LVL {level}</div>'
            f'<div class="gm-onb-role-pill" style="background:{LEVEL_COLORS[level]};">'
            f'<span class="gm-onb-picon">{LEVEL_ICONS[level]}</span>'
            f'<span class="gm-onb-rname">{role_label}</span>'
            f'</div>'
            f'{tagline}'
            f'{arrow}'
            f'</div>'
        )
    st.markdown(
        f'<div class="gm-onb-ladder-wrap"><div class="gm-onb-ladder">{"".join(chips)}</div></div>',
        unsafe_allow_html=True,
    )


def _render_step_journey():
    _dots(3)
    units_result = get_all_units()
    units = units_result.get("units", []) if units_result.get("success") else []

    st.markdown(f"### Your first milestone: Level {ACTIVE_LEVEL}")
    st.write(
        f"**{ACTIVE_ROLE}** breaks down into six SKKNI competency units. Finish "
        f"these, and Level {ACTIVE_LEVEL + 1} opens next."
    )

    if units:
        nodes = []
        for i, unit in enumerate(units):
            active = i == 0
            classes = "gm-onb-node active" if active else "gm-onb-node"
            lock = "" if active else '<div class="gm-onb-lock">🔒</div>'
            title = unit.get("title") or unit.get("unit_code", "")
            # Single unbroken line - see the comment in _render_ladder_preview
            # on why a blank line mid-block breaks Streamlit's HTML rendering.
            nodes.append(
                f'<div class="{classes}">'
                f'<div class="gm-onb-circ">{i + 1}</div>'
                f'<div class="gm-onb-lbl">{title}</div>'
                f'{lock}'
                f'</div>'
            )
        st.markdown(f'<div class="gm-onb-road">{"".join(nodes)}</div>', unsafe_allow_html=True)
    else:
        st.info("Unit list is temporarily unavailable — you'll see it on Learning Path.")

    st.markdown("**How each unit works**")
    st.markdown(
        """
        <div class="gm-onb-loop">
            <div class="gm-onb-lstep"><div class="gm-onb-ic">📝</div><div class="gm-onb-lbl">Mastery<br/>Measurement</div></div>
            <div class="gm-onb-arr">→</div>
            <div class="gm-onb-lstep"><div class="gm-onb-ic">📚</div><div class="gm-onb-lbl">Learn &amp;<br/>Practice</div></div>
            <div class="gm-onb-arr">→</div>
            <div class="gm-onb-lstep"><div class="gm-onb-ic">💬</div><div class="gm-onb-lbl">Reflect &amp;<br/>Discuss</div></div>
            <div class="gm-onb-arr">→</div>
            <div class="gm-onb-lstep"><div class="gm-onb-ic">🏁</div><div class="gm-onb-lbl">Post-Test</div></div>
        </div>
        <div class="gm-onb-legend">
            <span><i style="background:#9AA6B6"></i>Locked</span>
            <span><i style="background:#D5A23A"></i>In progress</span>
            <span><i style="background:#008000"></i>Mastered</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.write("")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("← Back", use_container_width=True, key="onb_j_back"):
            st.session_state.onboarding_step = 2
            st.rerun()
    with c2:
        if st.button("Continue", type="primary", use_container_width=True, key="onb_j_continue"):
            st.session_state.onboarding_step = 4
            st.rerun()


def _render_step_building():
    _dots(4)
    target_role = st.session_state.onboarding_target_role
    target_level = st.session_state.onboarding_target_level

    headline = f"Building your path to<br/>{target_role}…" if target_role else "Building your first milestone…"

    if target_role:
        route_html = f"""
        <div class="gm-onb-route">
            <div class="gm-onb-rnode"><div class="gm-onb-ic2">🖥️</div>{ACTIVE_ROLE}<br/><small>LVL {ACTIVE_LEVEL} · start</small></div>
            <div class="gm-onb-rarr">→</div>
            <div class="gm-onb-rnode goal"><div class="gm-onb-ic2">📈</div>{target_role}<br/><small>LVL {target_level} · goal</small></div>
        </div>
        """
    else:
        route_html = f"""
        <div class="gm-onb-route">
            <div class="gm-onb-rnode"><div class="gm-onb-ic2">🖥️</div>{ACTIVE_ROLE}<br/><small>LVL {ACTIVE_LEVEL} · start</small></div>
        </div>
        """

    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
      <style>
        .ring-wrap {{ display:flex; flex-direction:column; align-items:center; }}
        .ring {{
          --p:0; width:132px; height:132px; border-radius:50%;
          background:conic-gradient(#008000 calc(var(--p)*1%), #EAF0F5 0);
          display:flex; align-items:center; justify-content:center; margin-bottom:18px; position:relative;
        }}
        .ring::after {{ content:""; position:absolute; inset:12px; border-radius:50%; background:#fff; box-shadow:inset 0 0 0 1px #EAF0F5; }}
        .ring-pct {{ position:relative; z-index:1; font-size:28px; font-weight:800; color:#182133; display:flex; align-items:baseline; }}
        .ring-pct .sign {{ font-size:14px; font-weight:700; color:#63748C; margin-left:2px; }}
        .build-h {{ font-size:16.5px; font-weight:700; text-align:center; margin:0 0 16px; color:#182133; line-height:1.35; }}
        .build-line {{ font-size:12.5px; color:#63748C; display:flex; align-items:center; gap:8px; padding:6px 0; opacity:0; transform:translateY(6px); }}
        .build-line .chk {{ color:#008000; font-weight:700; flex:none; width:14px; }}
        .build-line.play {{ animation:mb-in .5s ease forwards; }}
        @keyframes mb-in {{ to {{ opacity:1; transform:translateY(0); }} }}
        .gm-onb-route {{ display:flex; align-items:center; justify-content:center; gap:12px; border-top:1px dashed #DCE3E8; padding-top:14px; margin-top:2px; }}
        .gm-onb-rnode {{ display:flex; flex-direction:column; align-items:center; gap:4px; font-size:10.5px; font-weight:700; color:#182133; text-align:center; line-height:1.2; }}
        .gm-onb-ic2 {{ width:34px; height:34px; border-radius:10px; background:#EAF0F5; display:flex; align-items:center; justify-content:center; font-size:15px; }}
        .gm-onb-rnode.goal .gm-onb-ic2 {{ background:#FBF3E1; box-shadow:0 0 0 2px #D5A23A; }}
        .gm-onb-rnode small {{ font-weight:600; color:#9AA6B6; font-size:9px; }}
        .gm-onb-rarr {{ color:#9AA6B6; font-size:14px; }}
      </style>
      <div class="ring-wrap">
        <div class="ring" id="ring"><div class="ring-pct"><span id="pct">0</span><span class="sign">%</span></div></div>
      </div>
      <div class="build-h">{headline}</div>
      <div>
        <div class="build-line" id="l1"><span class="chk">✓</span>Mapping your SKKNI competencies</div>
        <div class="build-line" id="l2"><span class="chk">✓</span>Sequencing Unit 1 — UI Implementation</div>
        <div class="build-line" id="l3"><span class="chk">✓</span>Calibrating your Mastery Measurement</div>
      </div>
      {route_html}
    </div>
    <script>
      (function(){{
        var reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        var ring = document.getElementById('ring');
        var pct = document.getElementById('pct');
        var lines = [document.getElementById('l1'), document.getElementById('l2'), document.getElementById('l3')];
        function finish() {{
          ring.style.setProperty('--p', 100);
          pct.textContent = '100';
          lines.forEach(function(l) {{ l.classList.add('play'); }});
        }}
        if (reduce) {{ finish(); }}
        else {{
          var dur = 1600, t0 = null;
          function step(ts) {{
            if (!t0) t0 = ts;
            var p = Math.min(1, (ts - t0) / dur);
            var val = Math.round(p * 100);
            ring.style.setProperty('--p', val);
            pct.textContent = val;
            if (p < 1) requestAnimationFrame(step);
          }}
          requestAnimationFrame(step);
          lines.forEach(function(l, i) {{ setTimeout(function() {{ l.classList.add('play'); }}, 350 + i * 420); }});
        }}
      }})();
    </script>
    """
    components.html(html, height=430)

    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("← Back", use_container_width=True, key="onb_b_back"):
            st.session_state.onboarding_step = 3
            st.rerun()
    with c2:
        if st.button("Continue", type="primary", use_container_width=True, key="onb_b_continue"):
            st.session_state.onboarding_step = 5
            st.rerun()


def _render_step_ready():
    _dots(5)
    first_name = (st.session_state.get("user_name") or "there").split(" ")[0]
    target_role = st.session_state.onboarding_target_role
    target_level = st.session_state.onboarding_target_level

    st.markdown(
        '<div style="text-align:center;font-size:40px;">🏅</div>',
        unsafe_allow_html=True,
    )
    st.markdown(f"<h3 style='text-align:center;'>You're all set, {first_name}!</h3>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:var(--text-muted);'>Here's what's ready:</p>", unsafe_allow_html=True)

    checks = []
    if target_role:
        checks.append(f"Career goal set — {target_role}, Level {target_level}")
    checks.append(f"Ladder unlocked from Level {ACTIVE_LEVEL} — {ACTIVE_ROLE}")

    st.markdown(
        "".join(
            f'<div class="gm-onb-check"><span class="gm-onb-tick">✓</span>{c}</div>' for c in checks
        ),
        unsafe_allow_html=True,
    )

    st.write("")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("← Back", use_container_width=True, key="onb_r_back"):
            st.session_state.onboarding_step = 4
            st.rerun()
    with c2:
        if st.button("Start Mastery Measurement →", type="primary", use_container_width=True, key="onb_r_test"):
            _finish_onboarding("test", target_role, target_level)
    if st.button("Explore Dashboard First", use_container_width=True, key="onb_r_profile"):
        _finish_onboarding("profile", target_role, target_level)

    st.markdown(
        "<p style='text-align:center;color:var(--text-muted);font-size:12px;margin-top:10px;'>"
        "You can revisit this journey map anytime from Learning Path.</p>",
        unsafe_allow_html=True,
    )


st.markdown('<div class="gm-onb-wrap">', unsafe_allow_html=True)
render_brand(auth_style=True)

with st.container(border=True):
    _step = st.session_state.onboarding_step
    if _step == 1:
        _render_step_welcome()
    elif _step == 2:
        _render_step_path()
    elif _step == 3:
        _render_step_journey()
    elif _step == 4:
        _render_step_building()
    else:
        _render_step_ready()

st.markdown('</div>', unsafe_allow_html=True)
