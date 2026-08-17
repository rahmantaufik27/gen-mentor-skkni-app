"""
Controller for free-notes API endpoints.

Thin pass-through to FreeNotesService, matching the other controllers'
convention of normalizing exceptions into {"success": False, "error": ...}.
"""

from typing import Dict, Optional

from services.free_notes_service import FreeNotesService


class FreeNotesController:
    """Controller for user-authored free-note operations."""

    def __init__(self, free_notes_service: FreeNotesService):
        self.free_notes_service = free_notes_service

    def create_note(self, user_id: str, category: str, content_html: str) -> Dict:
        try:
            return self.free_notes_service.create_note(user_id, category, content_html)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_notes(self, user_id: str, category: Optional[str] = None) -> Dict:
        try:
            return self.free_notes_service.list_notes(user_id, category)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def update_note(self, user_id: str, note_id: str, content_html: str) -> Dict:
        try:
            return self.free_notes_service.update_note(user_id, note_id, content_html)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_note(self, user_id: str, note_id: str) -> Dict:
        try:
            return self.free_notes_service.delete_note(user_id, note_id)
        except Exception as e:
            return {"success": False, "error": str(e)}
