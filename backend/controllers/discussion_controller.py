"""
Controller for unit-discussion API endpoints.

Thin pass-through to DiscussionService, matching the other controllers'
convention of normalizing exceptions into {"success": False, "error": ...}.
"""

from typing import Dict, Optional

from services.discussion_service import DiscussionService


class DiscussionController:
    """Controller for peer discussion post operations."""

    def __init__(self, discussion_service: DiscussionService):
        self.discussion_service = discussion_service

    def create_post(
        self, user_id: str, unit_code: str, body: str, parent_post_id: Optional[str] = None,
        material_id: Optional[str] = None, material_title: Optional[str] = None,
    ) -> Dict:
        try:
            return self.discussion_service.create_post(
                user_id, unit_code, body, parent_post_id, material_id, material_title,
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_posts(self, unit_code: str, material_id: Optional[str] = None) -> Dict:
        try:
            return self.discussion_service.list_posts(unit_code, material_id)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_post_counts(self) -> Dict:
        try:
            return self.discussion_service.get_post_counts()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_material_post_counts(self, unit_code: str) -> Dict:
        try:
            return self.discussion_service.get_material_post_counts(unit_code)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def set_best_answer(self, user_id: str, reply_id: str, is_best: bool) -> Dict:
        try:
            return self.discussion_service.set_best_answer(user_id, reply_id, is_best)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_post(self, user_id: str, post_id: str) -> Dict:
        try:
            return self.discussion_service.delete_post(user_id, post_id)
        except Exception as e:
            return {"success": False, "error": str(e)}
