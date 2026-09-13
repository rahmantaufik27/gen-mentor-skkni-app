"""
Unit Discussion module (Learning Path -> Discussion) - the peer-to-peer Q&A
forum: one thread per SKKNI unit, so learners working on the same unit can
ask and help each other instead of learning in isolation. This is the
"Collaborative/Peer-Based Personalization" feature - see
backend/services/discussion_service.py for the CRUD this renders.

A discussion is always anchored to a Unit, and can optionally be narrowed
to one specific material within that unit (verified against Neo4j before
this was added: every material/Concept has exactly one parent Unit via
(Unit)-[:HAS_CONCEPT]->(Concept), so "per-material" is always presented as
a child of "per-unit", never picked on its own - see _render_material_picker).

Public entry point:
  - render_discussion(): a unit selector (every configured unit, labeled
    with its title and how many posts it has - so it works even before the
    user's first Test) plus a material picker within that unit (General
    Unit Discussion, or one specific material's thread), plus the selected
    scope's thread: search + sort, a new-post box, then each top-level post
    with a collapsed reply count, a reply box, a "mark best answer" action
    for the post's own author, and a Delete action visible only on the
    current user's own posts/replies.

Reading Materials' "💬 Discuss" button (components/reading_materials.py)
deep-links here by setting discussion_prefill_* in session_state before
switching to this page - see the prefill handling in render_discussion().
"""

from datetime import datetime

import streamlit as st

from utils.quiz_api import get_unit_code_map
from utils.materials_api import get_all_units, get_all_materials, material_source_id
from utils.discussion_api import (
    list_discussion_posts, create_discussion_post, delete_discussion_post,
    get_discussion_counts, get_material_discussion_counts, set_best_answer,
)
from utils.profile_api import profile_photo_url

# Basic Markdown (bold/italic/links) and fenced ```code``` blocks both
# render fine through st.markdown - this is just to make that discoverable,
# since nothing in the UI otherwise hints at it.
_FORMATTING_HINT = "Tip: **bold**, _italic_, and ```code blocks``` are all supported."

# Sentinel option value for "no specific material - the unit's general
# discussion" in the material picker (never collides with a real material
# id, which is always a url or "title|unit_code").
_GENERAL_SCOPE = "__general__"


def _relative_time(iso_date: str) -> str:
    """'2 hours ago' style label for recent posts, falling back to a plain
    date once a post is more than a week old (relative time stops being
    useful/scannable past that point)."""
    if not iso_date:
        return "-"
    try:
        when = datetime.fromisoformat(iso_date)
    except ValueError:
        return iso_date

    seconds = (datetime.now() - when).total_seconds()
    if seconds < 0:
        seconds = 0
    if seconds < 60:
        return "just now"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = int(minutes // 60)
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    days = int(hours // 24)
    if days < 7:
        return f"{days} day{'s' if days != 1 else ''} ago"
    return when.strftime("%d-%m-%Y")


def _get_unit_options() -> dict:
    """{unit_code: title} for every configured unit (static, not
    user-specific) - so the picker works even for a learner who hasn't
    taken a Test yet. Titles come from Neo4j's Unit nodes (see
    MaterialsService.get_all_units); falls back to the bare code map (no
    titles) if that's unavailable so the picker still works."""
    result = get_all_units()
    if result.get("success") and result.get("units"):
        return {u["unit_code"]: u.get("title") for u in result["units"] if u.get("unit_code")}

    code_map = get_unit_code_map()
    codes = sorted(set(code_map.get("unit_codes", {}).values())) if code_map.get("success") else []
    return {code: None for code in codes}


def render_discussion():
    """Render the unit + material selectors and the selected scope's thread."""
    unit_titles = _get_unit_options()
    if not unit_titles:
        st.error("Could not load the list of units. Please try again later.")
        return

    # One-shot deep-link prefill from Reading Materials' "Discuss" button -
    # popped so it doesn't keep re-forcing the selection after the user
    # picks something else. `nonce` forces the selectors to remount for a
    # NEW deep-link even if their key already existed with a different
    # value earlier this session (a Streamlit widget only honors `index=`
    # on a key's first mount, not on later reruns).
    prefill_unit = st.session_state.pop("discussion_prefill_unit", None)
    prefill_material_id = st.session_state.pop("discussion_prefill_material_id", None)
    prefill_material_title = st.session_state.pop("discussion_prefill_material_title", None)
    nonce = st.session_state.get("discussion_prefill_nonce", 0)

    counts_result = get_discussion_counts()
    counts = counts_result.get("counts", {}) if counts_result.get("success") else {}

    def _unit_label(code: str) -> str:
        title_part = f" — {unit_titles[code]}" if unit_titles.get(code) else ""
        count = counts.get(code, 0)
        post_word = "post" if count == 1 else "posts"
        return f"{code}{title_part}  ·  {count} {post_word}"

    unit_codes = sorted(unit_titles.keys())
    unit_index = unit_codes.index(prefill_unit) if prefill_unit in unit_codes else 0
    unit_code = st.selectbox(
        "Unit", unit_codes, index=unit_index, key=f"discussion_unit_select_{nonce}", format_func=_unit_label,
    )

    material_id, material_title = _render_material_picker(
        unit_code, nonce,
        prefill_material_id if unit_code == prefill_unit else None,
        prefill_material_title,
    )

    st.markdown("")
    _render_new_post_box(unit_code, material_id, material_title)

    result = list_discussion_posts(unit_code, material_id)
    if not result.get("success"):
        st.error(f"Failed to load discussion: {result.get('error', 'Unknown error')}")
        return

    posts = result.get("posts", [])
    if not posts:
        st.info("No posts yet here - be the first to ask a question or share something.")
        return

    st.markdown("")
    scope_key = f"{unit_code}_{material_id or 'general'}"
    posts = _apply_search_and_sort(posts, scope_key)
    if not posts:
        st.info("No posts match your search.")
        return

    for post in posts:
        _render_post(post, unit_code, material_id, material_title)


def _render_material_picker(unit_code: str, nonce: int, prefill_material_id: str, prefill_material_title: str):
    """
    General unit discussion, or one material's thread within it. A
    material is always presented nested under its unit (never picked on
    its own) - matches the graph's own (Unit)-[:HAS_CONCEPT]->(Concept)
    hierarchy, verified before this was built.

    Returns (material_id, material_title) - (None, None) for the general
    unit discussion, or (None, None) if the unit simply has no materials
    to scope to yet.
    """
    materials_result = get_all_materials()
    materials = (
        [m for m in materials_result.get("materials", []) if m.get("unit_code") == unit_code]
        if materials_result.get("success") else []
    )
    if not materials:
        return None, None

    counts_result = get_material_discussion_counts(unit_code)
    counts = counts_result.get("counts", {}) if counts_result.get("success") else {}

    options = [_GENERAL_SCOPE] + [material_source_id(m) for m in materials]
    titles_by_id = {material_source_id(m): m.get("title", "Untitled") for m in materials}

    def _label(option: str) -> str:
        if option == _GENERAL_SCOPE:
            return "💬 General Unit Discussion"
        count = counts.get(option, 0)
        return f"📄 {titles_by_id.get(option, 'Untitled')} · {count} post{'s' if count != 1 else ''}"

    default_index = options.index(prefill_material_id) if prefill_material_id in options else 0
    selected = st.selectbox(
        "Discussion scope", options, index=default_index,
        key=f"discussion_material_select_{unit_code}_{nonce}", format_func=_label,
    )

    if selected == _GENERAL_SCOPE:
        return None, None
    return selected, titles_by_id.get(selected, prefill_material_title)


def _apply_search_and_sort(posts: list, scope_key: str) -> list:
    """Search box (matches a post's own body OR any of its replies') +
    Newest/Oldest sort - both client-side, fine at this app's post volume."""
    search_col, sort_col = st.columns([3, 1])
    with search_col:
        query = st.text_input(
            "Search", key=f"discussion_search_{scope_key}",
            placeholder="🔍 Search this discussion…", label_visibility="collapsed",
        )
    with sort_col:
        newest_first = st.selectbox(
            "Sort", ["Newest first", "Oldest first"], key=f"discussion_sort_{scope_key}",
            label_visibility="collapsed",
        ) == "Newest first"

    if query.strip():
        needle = query.strip().lower()

        def _matches(post):
            if needle in (post.get("body") or "").lower():
                return True
            return any(needle in (r.get("body") or "").lower() for r in post.get("replies", []))

        posts = [p for p in posts if _matches(p)]

    return list(reversed(posts)) if newest_first else posts


def _render_new_post_box(unit_code: str, material_id: str, material_title: str):
    """Blank post box, reset (via a version-bumped widget key, same trick
    as components/free_notes.py) after each successful post so it doesn't
    keep showing what was just submitted."""
    scope_key = f"{unit_code}_{material_id or 'general'}"
    version_key = f"discussion_new_version_{scope_key}"
    version = st.session_state.get(version_key, 0)

    with st.container(border=True):
        if material_id:
            st.markdown(f"##### Ask or share something about *{material_title}*")
        else:
            st.markdown("##### Ask or share something")
        body = st.text_area(
            "Your post", key=f"discussion_new_{scope_key}_{version}",
            placeholder="Ask a question, or share something that helped you...",
            label_visibility="collapsed",
        )
        st.caption(_FORMATTING_HINT)
        if st.button("Post", key=f"discussion_post_btn_{scope_key}_{version}", type="primary"):
            if not (body or "").strip():
                st.toast("Write something before posting", icon="⚠️")
            else:
                result = create_discussion_post(unit_code, body, material_id=material_id, material_title=material_title)
                if result.get("success"):
                    st.session_state[version_key] = version + 1
                    st.toast("Posted")
                    st.rerun()
                else:
                    st.toast(f"Could not post: {result.get('error', 'error')}", icon="⚠️")


def _render_author_line(post: dict):
    """Avatar (the author's uploaded photo if they have one, else initials
    - reusing the app-wide .gm-avatar look) + name + a relative timestamp,
    all on one line."""
    author = post.get("author_name") or "Learner"
    initials = "".join(p[0] for p in author.split()[:2]).upper() or "?"
    if post.get("author_photo_path"):
        avatar_html = (
            f"<img class='gm-avatar gm-avatar-img' style='width:28px; height:28px;' "
            f"src='{profile_photo_url(post.get('user_id'))}'>"
        )
    else:
        avatar_html = f"<div class='gm-avatar' style='width:28px; height:28px; font-size:11px;'>{initials}</div>"
    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:8px; margin-bottom:4px;">
            {avatar_html}
            <div>
                <div style="font-weight:600; font-size:13.5px; line-height:1.2;">{author}</div>
                <div style="color:var(--text-muted); font-size:11.5px;">{_relative_time(post.get('created_at'))}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_reply(reply: dict, post_id: str, my_user_id: str, is_post_owner: bool):
    """One reply: author line, body, best-answer badge/marking, Delete."""
    card_kind = "best" if reply.get("is_best_answer") else "normal"
    with st.container(border=True, key=f"discussion_reply_card_{card_kind}_{reply['id']}"):
        if reply.get("is_best_answer"):
            st.markdown("<span class='gm-badge gm-badge-success'>✓ Best Answer</span>", unsafe_allow_html=True)
        _render_author_line(reply)
        st.markdown(reply.get("body", ""))

        action_cols = st.columns(3)
        col_idx = 0
        if is_post_owner:
            with action_cols[col_idx]:
                if reply.get("is_best_answer"):
                    if st.button("Unmark best answer", key=f"discussion_unbest_{reply['id']}"):
                        _set_best_and_refresh(reply["id"], False)
                else:
                    if st.button("Mark as best answer", key=f"discussion_best_{reply['id']}"):
                        _set_best_and_refresh(reply["id"], True)
            col_idx += 1
        if str(reply.get("user_id")) == my_user_id:
            with action_cols[col_idx]:
                if st.button("Delete", key=f"discussion_delete_{reply['id']}"):
                    _delete_and_refresh(reply["id"])


def _render_post(post: dict, unit_code: str, material_id: str, material_title: str):
    """One top-level post: author/timestamp, body, a collapsed replies
    section (count in the label, existing replies + a reply box inside),
    and a Delete action for the post's own author."""
    my_user_id = str(st.session_state.get("userId") or "")
    post_id = post["id"]
    is_post_owner = str(post.get("user_id")) == my_user_id
    replies = post.get("replies", [])
    has_best_answer = any(r.get("is_best_answer") for r in replies)

    with st.container(border=True):
        header_col, delete_col = st.columns([5, 1])
        with header_col:
            _render_author_line(post)
        with delete_col:
            if is_post_owner:
                if st.button("Delete", key=f"discussion_delete_{post_id}", use_container_width=True):
                    _delete_and_refresh(post_id)

        st.markdown(post.get("body", ""))
        if has_best_answer:
            st.caption("✓ This post has a marked best answer")

        reply_label = "💬 Reply" if not replies else f"💬 {len(replies)} repl{'y' if len(replies) == 1 else 'ies'}"
        with st.expander(reply_label, expanded=False):
            for reply in replies:
                _render_reply(reply, post_id, my_user_id, is_post_owner)

            st.markdown("")
            reply_version_key = f"discussion_reply_version_{post_id}"
            reply_version = st.session_state.get(reply_version_key, 0)
            reply_body = st.text_area(
                "Your reply", key=f"discussion_reply_{post_id}_{reply_version}",
                label_visibility="collapsed", placeholder="Write a reply…",
            )
            st.caption(_FORMATTING_HINT)
            if st.button("Send reply", key=f"discussion_reply_btn_{post_id}_{reply_version}"):
                if not (reply_body or "").strip():
                    st.toast("Write something before replying", icon="⚠️")
                else:
                    result = create_discussion_post(
                        unit_code, reply_body, parent_post_id=post_id,
                        material_id=material_id, material_title=material_title,
                    )
                    if result.get("success"):
                        st.session_state[reply_version_key] = reply_version + 1
                        st.toast("Reply posted")
                        st.rerun()
                    else:
                        st.toast(f"Could not reply: {result.get('error', 'error')}", icon="⚠️")


def _set_best_and_refresh(reply_id: str, is_best: bool):
    result = set_best_answer(reply_id, is_best)
    if result.get("success"):
        st.toast("Marked as best answer" if is_best else "Unmarked")
        st.rerun()
    else:
        st.toast(f"Could not update: {result.get('error', 'error')}", icon="⚠️")


def _delete_and_refresh(post_id: str):
    result = delete_discussion_post(post_id)
    if result.get("success"):
        st.toast("Deleted")
        st.rerun()
    else:
        st.toast(f"Could not delete: {result.get('error', 'error')}", icon="⚠️")
