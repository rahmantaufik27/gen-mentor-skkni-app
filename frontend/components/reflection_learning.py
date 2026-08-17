"""
Reflection Learning module (Learning Path -> Reflection Learning).

Owns the Learning Reflection question form: config-driven sections (see
backend/data/reflection_questions.json) rendered with each question's saved
answer loaded, and a SINGLE Save/Update button at the end of the form that
persists every answer in one pass (upserting filled ones, clearing any the
user emptied) - independent create/edit/delete per answer, batched into one
action per the product's UX.

Public entry points:
  - render_reflection_learning(): the Reflection Learning page - the
    "Reflection & Action Plan" section (Immediate Application, Challenges
    Expected, Next Learning Action, Motivation Rating).
  - render_reflection_form(section_keys): generic renderer for one or more
    configured sections, reused by components/notes.py to show the "Cue
    Questions & Key Points" section on the Notes page's Free Notes tab. Both
    pages share the exact same backend (config + /api/reflection/* + the
    user_reflections table) - only the section(s) shown differ - so no
    reflection data is duplicated or lost by living on two pages.
"""

from datetime import datetime

import streamlit as st

from utils.reflection_api import (
    get_reflection_questions, get_reflection_answers,
    save_reflection_answer, delete_reflection_answer,
)


def _format_date(iso_date: str) -> str:
    if not iso_date:
        return "-"
    try:
        return datetime.fromisoformat(iso_date).strftime("%d-%m-%Y %H:%M")
    except ValueError:
        return iso_date


def render_reflection_form(section_keys: list):
    """
    Render the configured reflection section(s) whose key is in section_keys,
    each question loaded with its saved answer, plus a single Save/Update
    button at the end that persists the whole rendered form in one go.

    Args:
        section_keys: which data/reflection_questions.json section(s) to
            render here (e.g. ["cue_questions"] or ["reflection_action_plan"]).
    """
    questions_result = get_reflection_questions()
    if not questions_result.get("success"):
        st.error(f"Failed to load reflection questions: {questions_result.get('error', 'Unknown error')}")
        return

    answers_result = get_reflection_answers()
    if not answers_result.get("success"):
        st.error(f"Failed to load your reflections: {answers_result.get('error', 'Unknown error')}")
        return
    answers = answers_result.get("answers", {})

    sections = [s for s in questions_result.get("sections", []) if s.get("key") in section_keys]
    if not sections:
        return

    for section in sections:
        with st.container(border=True):
            st.markdown(f"##### {section.get('title', '')}")
            if section.get("description"):
                st.caption(section["description"])
            for question in section.get("questions", []):
                _render_reflection_question(question, answers.get(question["key"]))

    # --- Single action button for the whole form -------------------------
    # Scoped to just the questions rendered here, so the label (Save vs
    # Update) reflects THIS form's saved state, not any other section's.
    has_any_saved = any(
        q["key"] in answers for section in sections for q in section.get("questions", [])
    )
    st.markdown("")
    button_label = "Update Reflection" if has_any_saved else "Save Reflection"
    if st.button(button_label, type="primary", use_container_width=True, key=f"refl_save_all_{'_'.join(section_keys)}"):
        _save_all_reflections(sections, answers)


def _save_all_reflections(sections: list, answers: dict):
    """Persist every answer in the form in one pass: upsert filled answers,
    delete ones the user emptied. Summarizes the outcome and reruns."""
    saved_count = 0
    cleared_count = 0
    errors = []

    for section in sections:
        for question in section.get("questions", []):
            qkey = question["key"]
            qtype = question.get("type", "text")
            widget_key = f"refl_input_{qkey}"
            was_saved = qkey in answers

            if qtype == "rating":
                value = st.session_state.get(widget_key, question.get("min", 1))
                result = save_reflection_answer(qkey, answer_number=int(value))
                if result.get("success"):
                    saved_count += 1
                else:
                    errors.append(f"{question.get('label', qkey)}: {result.get('error', 'error')}")
            else:
                text = (st.session_state.get(widget_key, "") or "").strip()
                if text:
                    result = save_reflection_answer(qkey, answer_text=text)
                    if result.get("success"):
                        saved_count += 1
                    else:
                        errors.append(f"{question.get('label', qkey)}: {result.get('error', 'error')}")
                elif was_saved:
                    # User emptied a previously-saved answer -> clear it.
                    result = delete_reflection_answer(qkey)
                    if result.get("success"):
                        cleared_count += 1
                    else:
                        errors.append(f"{question.get('label', qkey)}: {result.get('error', 'error')}")

    if errors:
        st.toast(f"Some answers couldn't be saved: {errors[0]}", icon="⚠️")
    else:
        summary = f"Reflection saved ({saved_count} answer{'s' if saved_count != 1 else ''}"
        summary += f", {cleared_count} cleared)" if cleared_count else ")"
        st.toast(summary)
    st.rerun()


def _render_reflection_question(question: dict, saved: dict):
    """Render one reflection question with its input and saved state (no
    per-question buttons - the whole form is saved by a single button below)."""
    qkey = question["key"]
    qtype = question.get("type", "text")
    widget_key = f"refl_input_{qkey}"
    has_saved = saved is not None

    label = question.get("label")
    if label:
        st.markdown(f"**{label}**")
    st.markdown(question.get("text", ""))

    if qtype == "rating":
        lo, hi = int(question.get("min", 1)), int(question.get("max", 5))
        default_val = int(saved["answer_number"]) if (has_saved and saved.get("answer_number") is not None) else lo
        st.slider(
            "Your rating", min_value=lo, max_value=hi, value=default_val,
            key=widget_key, label_visibility="collapsed",
        )
    else:
        default_text = saved.get("answer_text") if has_saved else ""
        st.text_area(
            "Your answer", value=default_text or "", key=widget_key,
            label_visibility="collapsed", placeholder="Type your answer…",
        )

    if has_saved:
        st.caption(f"Saved {_format_date(saved.get('updated_at') or saved.get('created_at'))}")

    st.markdown("")


def render_reflection_learning():
    """Render the Reflection Learning page: both the Cue Questions & Key
    Points section and the Reflection & Action Plan section (Immediate
    Application, Challenges Expected, Next Learning Action, Motivation
    Rating), rendered together as ONE form with a single Save/Update button
    at the bottom - passing both section keys to render_reflection_form in
    one call (instead of one call per section) is what collapses the two
    previously-separate Submit buttons into one. Same questions, same
    backend (config + /api/reflection/* + user_reflections table), so no
    reflection data changes hands."""
    st.markdown("#### 🧭 Reflection Learning")
    st.caption(
        "Turn today's learning into a concrete action plan. Answers are saved "
        "to your account and loaded when you return - fill in the form and "
        "save it all at once at the bottom."
    )
    render_reflection_form(["cue_questions", "reflection_action_plan"])
