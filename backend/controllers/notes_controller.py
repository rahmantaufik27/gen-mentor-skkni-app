"""
Controller for Notes API endpoints.

Thin pass-through to NotesService, matching the other controllers' convention
of normalizing exceptions into {"success": False, "error": ...}.
"""

from typing import Dict, Optional

from services.notes_service import NotesService


class NotesController:
    """Controller for notes/bookmarks operations."""

    def __init__(self, notes_service: NotesService):
        self.notes_service = notes_service

    def create_note(self, user_id, source_type, source_id, snapshot_text, title=None, source_ref=None) -> Dict:
        try:
            return self.notes_service.create_note(user_id, source_type, source_id, snapshot_text, title, source_ref)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_notes(self, user_id: str, source_type: Optional[str] = None) -> Dict:
        try:
            return self.notes_service.list_notes(user_id, source_type)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_saved_source_ids(self, user_id: str, source_type: Optional[str] = None) -> Dict:
        try:
            return self.notes_service.get_saved_source_ids(user_id, source_type)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_note(self, user_id, note_id=None, source_type=None, source_id=None) -> Dict:
        try:
            return self.notes_service.delete_note(user_id, note_id, source_type, source_id)
        except Exception as e:
            return {"success": False, "error": str(e)}
