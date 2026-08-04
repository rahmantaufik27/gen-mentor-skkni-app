"""
Service for reading materials and recommending them by mastery gap.

Materials now live in the Neo4j knowledge graph (see services/neo4j_service.py
and scripts/seed_neo4j.py) instead of data/materials.json - Neo4j is the
runtime source for both "All Materials" and "Recommended for You". The
recommendation engine itself (Neo4jService.get_recommended_materials) is
injected/swappable: this service's public contract (get_all_materials,
get_recommended_materials) is unchanged, so neither the API layer nor the
frontend needed to change to pick this up.
"""

from typing import Dict, List, Optional

from services.mastery_service import MasteryService
from services.neo4j_service import Neo4jService, get_neo4j_service


class MaterialsService:
    """Reads materials from Neo4j and cross-references them with unit mastery."""

    def __init__(self, mastery_service: Optional[MasteryService] = None, neo4j_service: Optional[Neo4jService] = None):
        # MasteryService (Postgres, the source of truth) is used only to
        # determine "has this user mastered everything" - the actual
        # material list/ranking comes from Neo4j.
        self.mastery_service = mastery_service or MasteryService()
        self.neo4j_service = neo4j_service or get_neo4j_service()

    def get_all_materials(self) -> List[Dict]:
        """Return every material in the Neo4j knowledge graph, unfiltered."""
        return self.neo4j_service.get_all_materials()

    def get_recommended_materials(self, user_id: str) -> Dict:
        """
        Materials for units that are currently Remedial (i.e. have not yet
        reached their target Bloom level), prioritized by Neo4jService
        (Remedial units first, then lowest knowledge level first).

        Returns:
            {"materials": [...], "all_mastered": bool}
        """
        summary = self.mastery_service.get_user_mastery_summary(user_id)
        all_mastered = bool(summary.get("units")) and all(
            u["mastery_status"] == "Mastered" for u in summary.get("units", [])
        )

        recommended = self.neo4j_service.get_recommended_materials(user_id)

        return {
            "materials": recommended,
            "all_mastered": all_mastered,
        }
