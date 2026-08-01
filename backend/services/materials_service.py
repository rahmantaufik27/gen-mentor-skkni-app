"""
Service for loading reading materials and recommending them by mastery gap.

Materials are read fresh from data/materials.json on every call (no in-memory
cache), so new materials can be added or edited without restarting the server -
the file is treated as dynamic content, not code.
"""

import json
import os
from typing import Dict, List, Optional

from services.mastery_service import MasteryService


def _truncate_unit_code(unit_code: str) -> str:
    """Reduce a full unit code (e.g. 'J.620100.010.01') to its 3-segment main
    code, matching the format used by MasteryService/knowledge_target.json."""
    parts = (unit_code or "").split(".")
    return ".".join(parts[:3]) if len(parts) >= 3 else unit_code


class MaterialsService:
    """Loads reading materials and cross-references them with unit mastery."""

    def __init__(self, mastery_service: Optional[MasteryService] = None):
        # Own MasteryService instance - this module stays self-contained so
        # other learning methods can be added later without depending on it.
        self.mastery_service = mastery_service or MasteryService()

    def _materials_path(self) -> str:
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(backend_dir, "data", "materials.json")

    def get_all_materials(self) -> List[Dict]:
        """Return every material from data/materials.json, unfiltered."""
        path = self._materials_path()
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []

    def get_recommended_materials(self, user_id: str) -> Dict:
        """
        Materials for units that are currently Remedial (i.e. have not yet
        reached their target Bloom level), annotated with that unit's
        mastery info so the frontend can explain why each was recommended.

        Returns:
            {"materials": [...], "all_mastered": bool}
        """
        summary = self.mastery_service.get_user_mastery_summary(user_id)
        units_by_code = {u["unit_code"]: u for u in summary.get("units", [])}
        remedial_codes = {
            code for code, u in units_by_code.items() if u["mastery_status"] == "Remedial"
        }

        recommended = []
        for material in self.get_all_materials():
            unit_code = _truncate_unit_code(material.get("unit_code", ""))
            if unit_code in remedial_codes:
                unit_info = units_by_code[unit_code]
                recommended.append({
                    **material,
                    "mastery_status": unit_info["mastery_status"],
                    "target_level": unit_info["target_level"],
                    "unit_mastery_level": unit_info["unit_mastery_level"],
                })

        return {
            "materials": recommended,
            "all_mastered": len(remedial_codes) == 0,
        }
