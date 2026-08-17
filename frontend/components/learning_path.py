"""
Learning Path module.

LEARNING_METHODS is the single source of truth for the Learning Path
sub-features (Reading Materials, Learning with Chatbot Assistance,
Practice with Generative Questions, Cue Questions, Key Points, Reflection
Learning): their sidebar labels/grouping (via get_learning_path_submenu())
and their render functions. Each method is its own dedicated full page
(pages/reading_materials.py, pages/chatbot.py, pages/practice.py,
pages/cue_questions.py, pages/key_points.py, pages/reflection_learning.py)
rather than content switched inside Learning Path - Learning Path itself is
a separate landing page (pages/learning_path.py).

Cue Questions and Key Points share "group": "notes", which
get_learning_path_submenu() nests into one "Notes" entry - rendered by
utils/theme.py::render_sidebar_nav() as an expandable/dropdown submenu
(st.expander) rather than two flat sidebar buttons. Each is still its own
page/current_page value exactly like every other entry - only the sidebar
presentation is nested.

Practice's Start button is enabled/disabled based on Test eligibility - see
utils/gating.py (components/practice.py enforces it; the menu entry itself
always stays visible/clickable).

Adding a new learning method later: add an entry to LEARNING_METHODS
(optionally with a "group" to nest it under a shared expandable submenu
entry), create its own pages/<name>.py (follow the existing pattern - see
any of the above), and add one elif branch to pages/learner_profile.py's
routing - no changes needed to the other methods or to the sidebar.
"""

from components.reading_materials import render_reading_materials
from components.practice import render_practice
from components.chatbot import render_chatbot
from components.cue_questions import render_cue_questions
from components.key_points import render_key_points
from components.reflection_learning import render_reflection_learning


LEARNING_METHODS = {
    "reading_materials": {"label": "Reading Materials", "render": render_reading_materials},
    "chatbot": {"label": "Learning with Chatbot Assistance", "render": render_chatbot},
    "practice": {"label": "Practice with Generative Questions", "render": render_practice},
    "cue_questions": {"label": "Cue Questions", "render": render_cue_questions, "group": "notes"},
    "key_points": {"label": "Key Points", "render": render_key_points, "group": "notes"},
    "reflection_learning": {"label": "Reflection Learning", "render": render_reflection_learning},
}

# Label shown for the sidebar group that nests entries sharing a "group" key
# (currently just "notes" -> Cue Questions / Key Points). See
# render_sidebar_nav in utils/theme.py for how groups render as an
# expandable/dropdown submenu.
GROUP_LABELS = {"notes": "Notes"}


def get_learning_path_submenu() -> list:
    """
    Sidebar submenu items for Learning Path, derived from LEARNING_METHODS.

    Entries with no "group" become a plain {"key", "label"} nav item.
    Entries sharing a "group" are nested together into one
    {"label", "children": [...]} group item (rendered as an expandable
    submenu), placed at the position of the group's first member.
    """
    items = []
    group_items = {}  # group name -> its group item dict, already appended to items
    for key, method in LEARNING_METHODS.items():
        group = method.get("group")
        if not group:
            items.append({"key": key, "label": method["label"]})
            continue
        if group not in group_items:
            group_item = {"label": GROUP_LABELS.get(group, group.title()), "children": []}
            group_items[group] = group_item
            items.append(group_item)
        group_items[group]["children"].append({"key": key, "label": method["label"]})
    return items
