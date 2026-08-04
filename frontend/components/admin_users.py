"""
Admin user management: search/filter the user list, update a single user's
inference_method (DBN/Manual), or apply a bulk change to every user at once.

Self-contained module: exposes render_admin_users() as its only public
entry point, following the same pattern as components/reading_materials.py.
Used exclusively by the admin module (pages/admin_dashboard.py) - never by
the learner interface.
"""

import streamlit as st

from utils.admin_api import get_all_users, update_inference_method, update_all_users_inference_method

INFERENCE_METHODS = ["DBN", "Manual"]


def _render_bulk_action(total_users: int):
    """Bulk action: set inference_method for every user at once."""
    with st.container(border=True):
        st.markdown("###### Bulk Update")
        st.caption(f"Applies to all {total_users} user(s) - per-user updates below still work independently.")
        col1, col2 = st.columns([3, 1])
        with col1:
            bulk_method = st.selectbox(
                "Set inference_method for all users to:",
                options=INFERENCE_METHODS,
                key="bulk_inference_method",
                label_visibility="collapsed",
            )
        with col2:
            if st.button("Apply to All", type="primary", use_container_width=True, key="bulk_apply_btn"):
                result = update_all_users_inference_method(bulk_method)
                if result.get("success"):
                    st.success(result.get("message", f"Updated all users to {bulk_method}"))
                    st.rerun()
                else:
                    st.error(result.get("error", "Bulk update failed"))


def _render_search_and_filter(users: list) -> list:
    """Search by name/email and filter by current inference_method. Returns the filtered list."""
    col1, col2 = st.columns([3, 1])
    with col1:
        search = st.text_input(
            "Search",
            key="admin_user_search",
            placeholder="Search by name or email...",
            label_visibility="collapsed",
        )
    with col2:
        method_filter = st.selectbox(
            "Filter",
            options=["All"] + INFERENCE_METHODS,
            key="admin_method_filter",
            label_visibility="collapsed",
        )

    filtered = users
    if search.strip():
        query = search.strip().lower()
        filtered = [
            u for u in filtered
            if query in (u.get("full_name") or "").lower() or query in (u.get("email") or "").lower()
        ]
    if method_filter != "All":
        filtered = [u for u in filtered if u.get("inference_method") == method_filter]

    return filtered


def _render_user_row(user: dict):
    """A single user's row: name/email, an inference_method selector, and a Save button."""
    with st.container(border=True):
        col1, col2, col3 = st.columns([3, 2, 1])

        with col1:
            st.markdown(f"**{user.get('full_name', 'Unknown')}**")
            st.caption(user.get("email", ""))

        with col2:
            current_method = user.get("inference_method") or "DBN"
            index = INFERENCE_METHODS.index(current_method) if current_method in INFERENCE_METHODS else 0
            selected_method = st.selectbox(
                "Inference Method",
                options=INFERENCE_METHODS,
                index=index,
                key=f"inference_method_{user['id']}",
                label_visibility="collapsed",
            )

        with col3:
            if st.button("Save", key=f"save_inference_{user['id']}", use_container_width=True):
                save_result = update_inference_method(user["id"], selected_method)
                if save_result.get("success"):
                    st.success(f"Updated {user.get('full_name', 'user')}'s inference method to {selected_method}")
                    st.rerun()
                else:
                    st.error(save_result.get("error", "Failed to update inference method"))


def render_admin_users():
    """Render user management: bulk action, search/filter, and per-user rows."""
    result = get_all_users()

    if not result.get("success"):
        st.error(f"Failed to load users: {result.get('error', 'Unknown error')}")
        return

    users = result.get("users", [])
    if not users:
        st.info("No users found.")
        return

    _render_bulk_action(total_users=len(users))
    st.markdown("")

    filtered_users = _render_search_and_filter(users)
    st.caption(f"Showing {len(filtered_users)} of {len(users)} user(s)")

    if not filtered_users:
        st.info("No users match your search/filter.")
        return

    for user in filtered_users:
        _render_user_row(user)
