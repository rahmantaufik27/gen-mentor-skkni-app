"""
Controller for reading-materials endpoints.

Thin pass-through to MaterialsService, matching the QuizController/
AuthController convention of normalizing exceptions into
{"success": False, "error": ...}.
"""

from services.materials_service import MaterialsService


class MaterialsController:
    """Controller for reading-materials operations."""

    def __init__(self, materials_service: MaterialsService):
        self.materials_service = materials_service

    def get_all_materials(self) -> dict:
        """Get every reading material."""
        try:
            materials = self.materials_service.get_all_materials()
            return {"success": True, "materials": materials}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_recommended_materials(self, user_id: str) -> dict:
        """Get materials recommended based on the user's current mastery gaps."""
        try:
            result = self.materials_service.get_recommended_materials(user_id)
            return {"success": True, **result}
        except Exception as e:
            return {"success": False, "error": str(e)}
