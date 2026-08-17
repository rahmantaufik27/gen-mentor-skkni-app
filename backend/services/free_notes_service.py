"""
Free notes service.

Standalone CRUD over the dedicated user_free_notes table (see
migrations/009_create_user_free_notes_table.py) for user-authored WYSIWYG
notes: the "Free Question" tab (Cue Questions page) and the "Free Notes" tab
(Key Points page). Unlike NotesService (bookmarks a source) or
ReflectionService (answers fixed questions), this is pure user-authored rich
text with no source reference - just a category and HTML content.

Every query is scoped to user_id, so one user can never read or modify
another user's free notes.
"""

import re
from typing import Dict, Optional
from uuid import uuid4

from config.database import execute_query

# The two supported categories - which tab a free note belongs to.
CATEGORY_QUESTION = "question"      # Cue Questions -> Free Question
CATEGORY_KEY_POINTS = "key_points"  # Key Points -> Free Notes
VALID_CATEGORIES = {CATEGORY_QUESTION, CATEGORY_KEY_POINTS}

_TAG_RE = re.compile(r"<[^>]*>")
_HTML_WS_RE = re.compile(r"&nbsp;|\s+")


def _has_content(html: Optional[str]) -> bool:
    """
    True if the HTML has any real text once tags/whitespace/&nbsp; are
    stripped. A plain `.strip()` on the raw HTML isn't enough - the Quill
    editor represents an "empty" note as markup like '<p></p>' or
    '<p><br></p>', which is a non-empty string but has no actual content.
    """
    text_only = _TAG_RE.sub("", html or "")
    text_only = _HTML_WS_RE.sub("", text_only)
    return bool(text_only)


class FreeNotesService:
    """CRUD for user-authored free-form (WYSIWYG) notes."""

    def create_note(self, user_id: str, category: str, content_html: str) -> Dict:
        """Create a new free note. Returns {"success": True, "note_id": str}."""
        if category not in VALID_CATEGORIES:
            return {"success": False, "error": f"Invalid category '{category}'"}
        if not _has_content(content_html):
            return {"success": False, "error": "Note content cannot be empty"}
        content_html = content_html.strip()

        try:
            note_id = str(uuid4())
            execute_query(
                """
                INSERT INTO user_free_notes (id, user_id, category, content_html)
                VALUES (%s, %s, %s, %s)
                """,
                (note_id, user_id, category, content_html),
            )
            return {"success": True, "note_id": note_id}
        except Exception as e:
            return {"success": False, "error": f"Failed to save note: {str(e)}"}

    def list_notes(self, user_id: str, category: Optional[str] = None) -> Dict:
        """List a user's free notes, newest first, optionally filtered by category."""
        if category is not None and category not in VALID_CATEGORIES:
            return {"success": False, "error": f"Invalid category '{category}'"}

        try:
            if category:
                rows = execute_query(
                    """
                    SELECT id, category, content_html, created_at, updated_at
                    FROM user_free_notes WHERE user_id = %s AND category = %s
                    ORDER BY updated_at DESC
                    """,
                    (user_id, category),
                    fetch=True,
                ) or []
            else:
                rows = execute_query(
                    """
                    SELECT id, category, content_html, created_at, updated_at
                    FROM user_free_notes WHERE user_id = %s
                    ORDER BY updated_at DESC
                    """,
                    (user_id,),
                    fetch=True,
                ) or []

            notes = [
                {
                    "id": str(note_id),
                    "category": cat,
                    "content_html": content_html,
                    "created_at": created_at.isoformat() if created_at else None,
                    "updated_at": updated_at.isoformat() if updated_at else None,
                }
                for note_id, cat, content_html, created_at, updated_at in rows
            ]
            return {"success": True, "notes": notes}
        except Exception as e:
            return {"success": False, "error": f"Failed to list notes: {str(e)}"}

    def update_note(self, user_id: str, note_id: str, content_html: str) -> Dict:
        """Update an existing free note's content (scoped to the owning user)."""
        if not _has_content(content_html):
            return {"success": False, "error": "Note content cannot be empty"}
        content_html = content_html.strip()
        try:
            execute_query(
                """
                UPDATE user_free_notes SET content_html = %s, updated_at = NOW()
                WHERE id = %s AND user_id = %s
                """,
                (content_html, note_id, user_id),
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"Failed to update note: {str(e)}"}

    def delete_note(self, user_id: str, note_id: str) -> Dict:
        """Delete a free note (scoped to the owning user)."""
        if not note_id:
            return {"success": False, "error": "note_id is required"}
        try:
            execute_query(
                "DELETE FROM user_free_notes WHERE id = %s AND user_id = %s",
                (note_id, user_id),
            )
            return {"success": True, "deleted": True}
        except Exception as e:
            return {"success": False, "error": f"Failed to delete note: {str(e)}"}
