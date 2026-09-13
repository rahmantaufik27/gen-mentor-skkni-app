"""
Session-state utilities: default initialization for the in-memory
st.session_state values the app relies on.

REMOVED (200-concurrent-user scalability/correctness audit): this module
used to also have a JSON-file-backed persistence layer
(save_persistent_state()/load_persistent_state(), backed by a single
shared user_data/data_store.json) meant to survive a hard browser refresh.
It was a live bug, not just a scaling concern - main.py called
initialize_session_state() (which called load_persistent_state()
unconditionally) on EVERY rerun, for EVERY session, and that one file was
shared by the whole server process rather than being per-session. With
more than one person using the app at the same time, one user's next
click could silently overwrite their own userId/user_name/user_email/
logged_in with whatever another user's session had last written to that
file - a real identity/session mix-up, not a hypothetical one, and it
didn't need 200 concurrent users to trigger, just two. Removed outright
rather than "fixed" (e.g. by keying the file per-session) because
Streamlit's own st.session_state already covers what this was trying to
do (survive reruns within a session) without a shared file; surviving a
hard refresh would need a real per-user mechanism (a signed cookie,
Flask's own session) if it's wanted back, not a global file.

NOTE: goal/learning-path related helpers below (add_new_goal, change_selected_goal_id,
etc.) belong to a separate, currently-unused goal-planning subsystem - unrelated
to the active auth/quiz/mastery flow.
"""

import streamlit as st
from collections import defaultdict
import config


def _normalize_goal_structure(goal: dict) -> dict:
    """Ensure goal dict has all required fields, adding defaults for missing ones.
    
    This handles migration from older versions that may be missing fields.
    """
    required_fields = {
        "id": 0,
        "learning_goal": "",
        "skill_gaps": [],
        "learner_profile": {},
        "learning_path": [],
        "is_completed": False,
        "is_deleted": False,
    }
    for field, default_value in required_fields.items():
        if field not in goal:
            goal[field] = default_value
    return goal


def initialize_session_state():
    for key in ["if_complete_onboarding", "is_learner_profile_ready", "is_learning_path_ready", "is_skill_gap_ready", "is_knowledge_document_ready"]:
        if key not in st.session_state:
            st.session_state[key] = False

    if "backend_endpoint" not in st.session_state:
        st.session_state["backend_endpoint"] = config.backend_endpoint

    if "available_models" not in st.session_state:
        st.session_state["available_models"] = ["OpenAI/GPT-4o"]

    if "llm_type" not in st.session_state:
        if len(st.session_state["available_models"]) > 0:
            st.session_state["llm_type"] = st.session_state["available_models"][0]
        else:
            st.session_state["llm_type"] = "None"

    if "userId" not in st.session_state:
        st.session_state["userId"] = "TestUser"  # placeholder until login sets a real user UUID
        
    if "sample_number" not in st.session_state:
        st.session_state["sample_number"] = 2
        
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False

    if "show_chatbot" not in st.session_state:
        st.session_state["show_chatbot"] = True

    if "tutor_messages" not in st.session_state:
        st.session_state["tutor_messages"] = []

    if "selected_page" not in st.session_state:
        st.session_state["selected_page"] = "Onboarding"

    if "goals" not in st.session_state:
        st.session_state["goals"] = []
    
    if "current_page" not in st.session_state:
        st.session_state["current_page"] = "profile"  # default tab shown in the app shell (utils/theme.py)
        
    if "document_caches" not in st.session_state:
        st.session_state["document_caches"] = {}

    if "session_learning_times" not in st.session_state:
        st.session_state["session_learning_times"] = {}

    for key in ["learner_information", "learner_information_pdf", "learner_information_text", "learner_occupation"]:
        if key not in st.session_state:
            st.session_state[key] = ""

    if "if_refining_learning_goal" not in st.session_state:
        st.session_state["if_refining_learning_goal"] = False

    if "if_rescheduling_learning_path" not in st.session_state:
        st.session_state["if_rescheduling_learning_path"] = False

    if "if_updating_learner_profile" not in st.session_state:
        st.session_state["if_updating_learner_profile"] = False

    for key in ["selected_goal_id", "selected_session_id", "selected_point_id"]:
        if key not in st.session_state:
            st.session_state[key] = 0

    if "to_add_goal" not in st.session_state:
        reset_to_add_goal()

    if 'learned_skills_history' not in st.session_state:
        st.session_state['learned_skills_history'] = {}

def get_new_goal_uid():
    return max(goal["id"] for goal in st.session_state.goals) + 1 if st.session_state.goals else 0

def reset_to_add_goal():
    st.session_state["to_add_goal"] = {
        "learning_goal": "",
        "skill_gaps": [],
        "learner_profile": {},
        "learning_path": [],
        "is_completed": False,
        "is_deleted": False
    }
    return st.session_state["to_add_goal"]


def index_goal_by_id(goal_id):
    goal_id_list = [goal["id"] for goal in st.session_state["goals"]]
    try:
        return goal_id_list.index(goal_id)
    except ValueError:
        return None

def change_selected_goal_id(new_goal_id):
    if new_goal_id == st.session_state["selected_goal_id"]:
        return
    goals = st.session_state["goals"]
    st.session_state["selected_goal_id"] = new_goal_id
    goal_id_list = [goal["id"] for goal in goals]
    goal_id_idx = goal_id_list.index(new_goal_id)
    st.session_state["learning_goal"] = goals[goal_id_idx]["learning_goal"]
    st.session_state["learner_profile"] = goals[goal_id_idx]["learner_profile"]
    st.session_state["skill_gaps"] = goals[goal_id_idx]["skill_gaps"]
    st.session_state["learning_path"] = goals[goal_id_idx]["learning_path"]
    st.session_state["selected_session_id"] = 0
    st.session_state["selected_point_id"] = 0
    # status
    st.session_state["is_learner_profile_ready"] = True if st.session_state["learner_profile"] else False
    st.session_state["is_learning_path_ready"] = True if st.session_state["learning_path"] else False
    st.session_state["is_skill_gap_ready"] = True if st.session_state["skill_gaps"] else False

def get_existing_goal_id_list():
    return [goal["id"] for goal in st.session_state["goals"]]

def add_new_goal(learning_goal="", skill_gaps=[], learner_profile={}, learning_path=[], is_completed=False, is_deleted=False, **kwargs):
    """Add a new goal to session state.
    
    Accepts **kwargs to handle extra parameters like 'id' from goal dict unpacking.
    The id is always generated fresh, not taken from the goal dict.
    """
    goal_uid = get_new_goal_uid()
    goal_info = {
        "id": goal_uid,
        "learning_goal": learning_goal,
        "skill_gaps": skill_gaps,
        "learner_profile": learner_profile,
        "learning_path": learning_path,
        "is_completed": is_completed,
        "is_deleted": is_deleted
    }
    st.session_state.goals.append(goal_info)
    goal_idx = index_goal_by_id(goal_uid)
    reset_to_add_goal()
    return goal_idx

def get_current_knowledge_point_uid():
    selected_gid = st.session_state["selected_goal_id"]
    selected_sid = st.session_state["selected_session_id"]
    selected_pid = st.session_state["selected_point_id"]
    return f"{selected_gid}-{selected_sid}-{selected_pid}"

def get_current_session_uid():
    selected_gid = st.session_state["selected_goal_id"]
    selected_sid = st.session_state["selected_session_id"]
    return f"{selected_gid}-{selected_sid}"
