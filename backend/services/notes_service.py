"""
Notes / bookmarks service.

Standalone CRUD over the dedicated user_notes table (see
migrations/007_create_user_notes_table.py). A note bookmarks one SPECIFIC piece
of learning content from a source (Reading Materials, Practice Questions, or
Chatbot Discussions) for the authenticated user.

Design goals (per task): modular, independent, and additive - it only reads and
writes its own user_notes table (never any existing table), so nothing about
Materials/Practice/Chatbot has to change for notes to work. The source content
is referenced by (source_type, source_id) and a JSONB source_ref for
open/return, plus a snapshot_text copy so the note stays understandable even if
the source UI changes.

Duplicate prevention is enforced at the DB level (UNIQUE(user_id, source_type,
source_id)); create_note treats an existing row as an idempotent success
(created=False) so the frontend toggle can call it without pre-checking.
"""

import json
from typing import Dict, List, Optional
from uuid import uuid4

from config.database import execute_query

# The three supported content sources.
VALID_SOURCE_TYPES = {"material", "question", "chat"}


class NotesService:
    """CRUD for user notes/bookmarks, one row per (user, source_type, source_id)."""

    def create_note(
        self,
        user_id: str,
        source_type: str,
        source_id: str,
        snapshot_text: str,
        title: Optional[str] = None,
        source_ref: Optional[Dict] = None,
    ) -> Dict:
        """
        Save a note for a specific piece of content. Idempotent: if the same
        (user, source_type, source_id) is already saved, it's treated as a
        success with created=False (no duplicate row) - see the UNIQUE
        constraint in migration 007.

        Returns:
            {"success": True, "created": bool, "note_id": str} or
            {"success": False, "error": str}
        """
        if source_type not in VALID_SOURCE_TYPES:
            return {"success": False, "error": f"Invalid source_type '{source_type}'"}
        if not source_id:
            return {"success": False, "error": "source_id is required"}
        if not snapshot_text:
            return {"success": False, "error": "snapshot_text is required"}

        try:
            existing = execute_query(
                "SELECT id FROM user_notes WHERE user_id = %s AND source_type = %s AND source_id = %s",
                (user_id, source_type, source_id),
                fetch=True,
            )
            if existing:
                return {"success": True, "created": False, "note_id": str(existing[0][0])}

            note_id = str(uuid4())
            execute_query(
                """
                INSERT INTO user_notes (id, user_id, source_type, source_id, title, snapshot_text, source_ref)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, source_type, source_id) DO NOTHING
                """,
                (
                    note_id, user_id, source_type, source_id, title, snapshot_text,
                    json.dumps(source_ref) if source_ref else None,
                ),
            )
            return {"success": True, "created": True, "note_id": note_id}
        except Exception as e:
            return {"success": False, "error": f"Failed to save note: {str(e)}"}

    def list_notes(self, user_id: str, source_type: Optional[str] = None) -> Dict:
        """
        List a user's notes, newest first, optionally filtered by source_type.

        Returns:
            {"success": True, "notes": [{id, source_type, source_id, title,
             snapshot_text, source_ref, created_at}]} or {"success": False, ...}
        """
        if source_type is not None and source_type not in VALID_SOURCE_TYPES:
            return {"success": False, "error": f"Invalid source_type '{source_type}'"}

        try:
            if source_type:
                rows = execute_query(
                    """
                    SELECT id, source_type, source_id, title, snapshot_text, source_ref, created_at
                    FROM user_notes WHERE user_id = %s AND source_type = %s
                    ORDER BY created_at DESC
                    """,
                    (user_id, source_type),
                    fetch=True,
                ) or []
            else:
                rows = execute_query(
                    """
                    SELECT id, source_type, source_id, title, snapshot_text, source_ref, created_at
                    FROM user_notes WHERE user_id = %s
                    ORDER BY created_at DESC
                    """,
                    (user_id,),
                    fetch=True,
                ) or []

            notes = [
                {
                    "id": str(nid),
                    "source_type": s_type,
                    "source_id": s_id,
                    "title": title,
                    "snapshot_text": snapshot_text,
                    # psycopg2 returns JSONB as a parsed dict already.
                    "source_ref": source_ref if isinstance(source_ref, dict) else (json.loads(source_ref) if source_ref else None),
                    "created_at": created_at.isoformat() if created_at else None,
                }
                for nid, s_type, s_id, title, snapshot_text, source_ref, created_at in rows
            ]
            return {"success": True, "notes": notes}
        except Exception as e:
            return {"success": False, "error": f"Failed to list notes: {str(e)}"}

    def get_saved_source_ids(self, user_id: str, source_type: Optional[str] = None) -> Dict:
        """
        Lightweight lookup of which content a user has already saved, so the
        frontend can render the Save/Remove toggle in the right state without
        pulling full note bodies.

        Returns:
            {"success": True, "keys": [{source_type, source_id}]} or error.
        """
        result = self.list_notes(user_id, source_type)
        if not result.get("success"):
            return result
        keys = [{"source_type": n["source_type"], "source_id": n["source_id"]} for n in result["notes"]]
        return {"success": True, "keys": keys}

    def delete_note(
        self,
        user_id: str,
        note_id: Optional[str] = None,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
    ) -> Dict:
        """
        Remove a note, either by note_id (from the Notes page) or by
        (source_type, source_id) (the Remove-from-Notes toggle on the content
        itself). Always scoped to user_id so a user can only delete their own.

        Returns:
            {"success": True, "deleted": bool} or {"success": False, "error": str}
        """
        try:
            if note_id:
                execute_query(
                    "DELETE FROM user_notes WHERE id = %s AND user_id = %s",
                    (note_id, user_id),
                )
                return {"success": True, "deleted": True}
            if source_type and source_id:
                execute_query(
                    "DELETE FROM user_notes WHERE user_id = %s AND source_type = %s AND source_id = %s",
                    (user_id, source_type, source_id),
                )
                return {"success": True, "deleted": True}
            return {"success": False, "error": "Provide note_id or (source_type, source_id) to delete"}
        except Exception as e:
            return {"success": False, "error": f"Failed to delete note: {str(e)}"}
