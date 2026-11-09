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
    LEVELS, ACTIVE_LEVEL, ACTIVE_ROLE, get_roles_for_level,
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

# English gloss for each of the 6 real SKKNI units under Assistant Web
# Developer (step 3's unit list) - titles themselves come from Neo4j in
# Bahasa Indonesia (the source standard's own language), so this is a
# static supplementary translation, keyed by the short "NNN.NN" suffix of
# unit_code the same way components/user_profile.py's chip labels are, not
# by the full code (whose prefix format isn't guaranteed stable).
UNIT_TITLE_EN = {
    "005.02": "Implementing the user interface",
    "010.01": "Running text-, graphics-, and multimedia-based programming language commands",
    "015.01": "Organizing functions, files, and other programming resources neatly",
    "016.01": "Writing code to guidelines and best practices",
    "017.02": "Implementing structured programming",
    "019.02": "Using pre-existing libraries or components",
}


def _unit_title_en(unit_code: str) -> str:
    short_code = ".".join(unit_code.split(".")[-2:]) if unit_code.count(".") >= 2 else unit_code
    return UNIT_TITLE_EN.get(short_code, "")


if "onboarding_step" not in st.session_state:
    st.session_state.onboarding_step = 1
if "onboarding_target_level" not in st.session_state:
    st.session_state.onboarding_target_level = None
if "onboarding_target_role" not in st.session_state:
    st.session_state.onboarding_target_role = None
# Step 2's "Current Role" mark (see _render_step_path) - an illustrative
# "where are you now" preview, separate from ACTIVE_LEVEL; None until the
# user explicitly marks one.
if "onboarding_current_level" not in st.session_state:
    st.session_state.onboarding_current_level = None
if "onboarding_current_role" not in st.session_state:
    st.session_state.onboarding_current_role = None


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
        f"Browse a level below, then mark where you are now and where you "
        f"want to go - nothing is set until you tap one of the two buttons. "
        f"Wherever you aim, your real progress always starts at the one "
        f"track open today — **{ACTIVE_ROLE}**."
    )

    # ONE row browses levels/roles - it's just a cursor, not a selection by
    # itself. "Current Role" and "Set as my goal" are the only things that
    # actually mark anything, so nothing on the ladder changes just from
    # moving this row around.
    browse_level = st.session_state.get("onb_browse_level", ACTIVE_LEVEL)
    cols = st.columns(len(LEVELS))
    for col, level in zip(cols, LEVELS):
        with col:
            if st.button(
                f"L{level}", key=f"onb_browse_{level}",
                type="primary" if browse_level == level else "secondary",
                use_container_width=True,
            ):
                st.session_state.onb_browse_level = level
                st.rerun()

    roles = get_roles_for_level(browse_level)
    browse_role = st.radio(
        "Roles at this level", roles, key=f"onb_role_radio_{browse_level}",
        label_visibility="collapsed",
    )

    m1, m2 = st.columns(2)
    with m1:
        with st.container(key="onb_mark_current_wrap"):
            if st.button("Current Role", use_container_width=True, key="onb_mark_current"):
                st.session_state.onboarding_current_level = browse_level
                st.session_state.onboarding_current_role = browse_role
                st.rerun()
    with m2:
        with st.container(key="onb_mark_goal_wrap"):
            if st.button("Set as my goal", use_container_width=True, key="onb_mark_goal"):
                st.session_state.onboarding_target_level = browse_level
                st.session_state.onboarding_target_role = browse_role
                st.rerun()

    current_level = st.session_state.onboarding_current_level or ACTIVE_LEVEL
    goal_level = st.session_state.onboarding_target_level
    goal_role = st.session_state.onboarding_target_role
    _render_ladder_preview(current_level, goal_level, goal_role)

    st.write("")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("← Back", use_container_width=True, key="onb_p_back"):
            st.session_state.onboarding_step = 1
            st.rerun()
    with c2:
        if st.button("Continue", type="primary", use_container_width=True, key="onb_p_continue"):
            st.session_state.onboarding_step = 3
            st.rerun()
    if st.button("Skip — decide later", use_container_width=True, key="onb_p_skip"):
        _finish_onboarding("profile")


def _render_ladder_preview(current_level: int, goal_level: int, goal_role: str):
    """The career ladder as a connected rail (levels 2-9): one continuous
    line - solid where the path is already open (up to ACTIVE_LEVEL), muted
    where it's still locked - with role cards zigzagging above/below their
    level's node so longer titles get real room instead of a cramped
    staircase of pills. Status (locked / available / goal / current-preview /
    top) is carried entirely by color and type, no per-level icon.

    `current_level` is an illustrative "where are you now" preview, separate
    from ACTIVE_LEVEL: picking a different one only adds a "You are here"
    marker on the ladder, it never changes what's actually open - only
    ACTIVE_LEVEL has real SKKNI units behind it today (see skkni_ladder.py).
    """
    steps = []
    for i, level in enumerate(LEVELS):
        roles_here = get_roles_for_level(level)
        role_label = goal_role if level == goal_level and goal_role in roles_here else roles_here[0]

        # Priority: goal > real active > preview-current > top > locked.
        # goal_level is checked FIRST because ACTIVE_LEVEL is itself
        # selectable as a goal (just not the default pick), and it must
        # still show a visible change when picked - otherwise selecting it
        # looks like the click did nothing. preview-current only shows its
        # own marker when it differs from ACTIVE_LEVEL, so the common case
        # (previewing from the real active level) looks exactly as before.
        if level == goal_level:
            status_class, status_text = "goal", "Your goal"
        elif level == ACTIVE_LEVEL:
            status_class, status_text = "available", "Available now"
        elif level == current_level:
            status_class, status_text = "current", "You are here"
        elif level == LEVELS[-1]:
            status_class, status_text = "top", "Top of ladder"
        else:
            status_class, status_text = "dim", "Locked"

        next_level_open = i + 1 < len(LEVELS) and LEVELS[i + 1] <= ACTIVE_LEVEL
        step_class = "gm-rail-step seg-open" if next_level_open else "gm-rail-step"
        card_side = "above" if i % 2 == 0 else "below"
        card = (
            f'<div class="gm-rail-card {card_side} {status_class}">'
            f'<div class="gm-rail-lvl">LVL {level}</div>'
            f'<div class="gm-rail-role">{role_label}</div>'
            f'<div class="gm-rail-status">{status_text}</div>'
            f'</div>'
        )
        stem = f'<div class="gm-rail-stem {card_side} {status_class}"></div>'
        node = f'<div class="gm-rail-node {status_class}">{level}</div>'
        # Built as ONE unbroken line (no blank lines mid-block) - Streamlit's
        # markdown renderer only treats a run of HTML as raw markup for as
        # long as it sees no blank line.
        steps.append(f'<div class="{step_class}">{card}{stem}{node}</div>')

    # Only shown when it differs from ACTIVE_LEVEL - in the common default
    # case (previewing from the real active level) there's no separate
    # "current" marker anywhere on the ladder, so the legend entry for it
    # would be pointing at nothing.
    current_legend = (
        '<span><i class="current"></i>You are here</span>'
        if current_level != ACTIVE_LEVEL else ""
    )
    st.markdown(
        '<div class="gm-rail-wrap">'
        '<div class="gm-rail-legend">'
        '<span><i class="open"></i>Open path</span>'
        '<span><i class="goal"></i>Your goal</span>'
        f'{current_legend}'
        '<span><i class="locked"></i>Locked</span>'
        '</div>'
        f'<div class="gm-rail-row">{"".join(steps)}</div>'
        '</div>',
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
            unit_code = unit.get("unit_code", "")
            title = unit.get("title") or unit_code
            title_en = _unit_title_en(unit_code)
            subtitle = f'<div class="gm-onb-lbl-en">{title_en}</div>' if title_en else ""
            # Single unbroken line - see the comment in _render_ladder_preview
            # on why a blank line mid-block breaks Streamlit's HTML rendering.
            nodes.append(
                f'<div class="{classes}">'
                f'<div class="gm-onb-circ">{i + 1}</div>'
                f'<div class="gm-onb-lbl">'
                f'<div class="gm-onb-lbl-id">{title}</div>'
                f'{subtitle}'
                f'</div>'
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
            <span><i style="background:var(--text-muted)"></i>Locked</span>
            <span><i style="background:var(--accent)"></i>In progress</span>
            <span><i style="background:var(--success)"></i>Mastered</span>
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

    if target_role and target_level != ACTIVE_LEVEL:
        route_html = f"""
        <div class="gm-onb-route">
            <div class="gm-onb-rnode"><div class="gm-onb-ic2">🖥️</div>{ACTIVE_ROLE}<br/><small>LVL {ACTIVE_LEVEL} · start</small></div>
            <div class="gm-onb-rarr">→</div>
            <div class="gm-onb-rnode goal"><div class="gm-onb-ic2">📈</div>{target_role}<br/><small>LVL {target_level} · goal</small></div>
        </div>
        """
    elif target_role:
        # Goal picked == the already-open starting level (Step 2 lets you
        # select ACTIVE_LEVEL too) - a start->goal arrow between two
        # identical nodes would just look broken, so show one node instead.
        route_html = f"""
        <div class="gm-onb-route">
            <div class="gm-onb-rnode goal"><div class="gm-onb-ic2">🖥️</div>{ACTIVE_ROLE}<br/><small>LVL {ACTIVE_LEVEL} · your goal</small></div>
        </div>
        """
    else:
        route_html = f"""
        <div class="gm-onb-route">
            <div class="gm-onb-rnode"><div class="gm-onb-ic2">🖥️</div>{ACTIVE_ROLE}<br/><small>LVL {ACTIVE_LEVEL} · start</small></div>
        </div>
        """

    html = f"""
    <div style="font-family:'Montserrat',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
      <style>
        .ring-wrap {{ display:flex; flex-direction:column; align-items:center; }}
        .ring {{
          --p:0; width:132px; height:132px; border-radius:50%;
          background:conic-gradient(#1C7A4D calc(var(--p)*1%), #EFEFEA 0);
          display:flex; align-items:center; justify-content:center; margin-bottom:18px; position:relative;
        }}
        .ring::after {{ content:""; position:absolute; inset:12px; border-radius:50%; background:#fff; box-shadow:inset 0 0 0 1px #EFEFEA; }}
        .ring-pct {{ position:relative; z-index:1; font-size:28px; font-weight:800; color:#1C2127; display:flex; align-items:baseline; }}
        .ring-pct .sign {{ font-size:14px; font-weight:700; color:#6B6F76; margin-left:2px; }}
        .build-h {{ font-size:16.5px; font-weight:700; text-align:center; margin:0 0 16px; color:#1C2127; line-height:1.35; }}
        .build-line {{ font-size:12.5px; color:#6B6F76; display:flex; align-items:center; gap:8px; padding:6px 0; opacity:0; transform:translateY(6px); }}
        .build-line .chk {{ color:#1C7A4D; font-weight:700; flex:none; width:14px; }}
        .build-line.play {{ animation:mb-in .5s ease forwards; }}
        @keyframes mb-in {{ to {{ opacity:1; transform:translateY(0); }} }}
        .gm-onb-route {{ display:flex; align-items:center; justify-content:center; gap:12px; border-top:1px dashed #E3E3DE; padding-top:14px; margin-top:2px; }}
        .gm-onb-rnode {{ display:flex; flex-direction:column; align-items:center; gap:4px; font-size:10.5px; font-weight:700; color:#1C2127; text-align:center; line-height:1.2; }}
        .gm-onb-ic2 {{ width:34px; height:34px; border-radius:10px; background:#EFEFEA; display:flex; align-items:center; justify-content:center; font-size:15px; }}
        .gm-onb-rnode.goal .gm-onb-ic2 {{ background:#FFF4CC; box-shadow:0 0 0 2px #FFC600; }}
        .gm-onb-rnode small {{ font-weight:600; color:#959A9F; font-size:9px; }}
        .gm-onb-rarr {{ color:#959A9F; font-size:14px; }}
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
