"""
Service for reading materials and recommending them by mastery gap.

Materials now live in the Neo4j knowledge graph (see services/neo4j_service.py
and scripts/seed_neo4j.py) instead of data/materials.json - Neo4j is the
runtime source for both "All Materials" and "Recommended for You". The
recommendation engine itself (Neo4jService.get_recommended_materials) is
injected/swappable: this service's public contract (get_all_materials,
get_recommended_materials) is unchanged, so neither the API layer nor the
frontend needed to change to pick this up.

get_recommended_materials() narrows Neo4j's Test-Remedial fetch down to
MasteryService.get_effective_remedial_units() - Remedial per the latest
Test AND not yet demonstrated Mastered in Practice since that Test - so
materials for a unit the learner has since mastered in Practice stop being
recommended without needing any change to the Neo4j query/sync itself.
"""

from typing import Dict, List, Optional

from services.mastery_service import MasteryService
from services.llm import get_llm_provider
from services.neo4j_service import Neo4jService, get_neo4j_service


def _truncate_unit_code(unit_code: Optional[str]) -> str:
    """Reduce a full unit code (e.g. 'J.620100.010.01') to its 3-segment main
    code, matching the convention used by Postgres/MasteryService."""
    parts = (unit_code or "").split(".")
    return ".".join(parts[:3]) if len(parts) >= 3 else (unit_code or "")


class MaterialsService:
    """Reads materials from Neo4j and cross-references them with unit mastery."""

    def __init__(self, mastery_service: Optional[MasteryService] = None, neo4j_service: Optional[Neo4jService] = None):
        # MasteryService (Postgres, the source of truth) is used to
        # determine "has this user mastered everything" and to narrow
        # recommendations to units still effectively Remedial (Test AND
        # Practice combined) - the actual material list/ranking still
        # comes from Neo4j.
        self.mastery_service = mastery_service or MasteryService()
        self.neo4j_service = neo4j_service or get_neo4j_service()

    def get_all_materials(self) -> List[Dict]:
        """Return every material in the Neo4j knowledge graph, unfiltered."""
        return self.neo4j_service.get_all_materials()

    def get_all_units(self) -> List[Dict]:
        """Every unit's code + human-readable title (static, not
        user-specific) - e.g. for the Discussion page's unit picker."""
        return self.neo4j_service.get_all_units()

    def generate_learning_material(self, unit_code: str, competency_name: str) -> Dict:
        """Generate learning material centered on a competency, using references as support."""
        unit_code = (unit_code or "").strip()
        competency_name = (competency_name or "").strip()
        if not unit_code:
            raise ValueError("Unit code is required.")
        if not competency_name:
            raise ValueError("Competency name is required.")

        examples = self.neo4j_service.get_existing_learning_materials(unit_code)
        if not examples:
            raise ValueError(f"No reference learning materials found for unit {unit_code}.")

        references = []
        remaining_chars = 6000
        for example in examples:
            if remaining_chars <= 0:
                break
            references.append(example[:remaining_chars])
            remaining_chars -= len(example)
        reference_text = "\n\n---\n\n".join(references)

        prompt = f"""You are a curriculum writer.
            UNIT CODE: {unit_code}
            CORE COMPETENCY: {competency_name}

            PRIMARY TASK:
            Write ONE learning material in Bahasa Indonesia (3-5 paragraphs) that directly teaches and develops the CORE COMPETENCY above. Keep every explanation, example, and learning objective centered on this competency.

            SUPPORTING REFERENCES:
            Use the key points below only as supplemental context, examples, or enriching details when they are relevant to the core competency. Do not let them replace, narrow, or redirect the material away from the core competency.
            {reference_text}

            Include practical examples and relevant Junior Web Developer case studies where appropriate. Avoid repeating reference text verbatim.

            Output format:
            TOPIC: <topik yang berpusat pada kompetensi>
            ---
            MATERIAL:
            <materi baru>"""
        print("unit_code:", unit_code)
        print("competency name:", competency_name)

        provider = get_llm_provider()
        content = provider.chat([{"role": "user", "content": prompt}])
        return {"material": content, "provider": provider.name}

    def get_recommended_materials(self, user_id: str) -> Dict:
        """
        Materials for units that are currently effectively Remedial - per
        the latest Test AND not yet demonstrated Mastered in Practice
        since that Test (see MasteryService.get_effective_remedial_units) -
        prioritized by Neo4jService (lowest knowledge level first).

        Returns:
            {"materials": [...], "all_mastered": bool}
        """
        summary = self.mastery_service.get_user_mastery_summary(user_id)
        has_attempts = bool(summary.get("success") and summary.get("has_attempts"))
        effective_remedial = set(summary.get("effective_remedial_units", []))

        recommended = self.neo4j_service.get_recommended_materials(user_id)
        recommended = [
            m for m in recommended if _truncate_unit_code(m.get("unit_code")) in effective_remedial
        ]

        # "All mastered" only once the learner has actually taken a Test -
        # a brand-new user has no effective_remedial_units either, but
        # hasn't earned this message yet (see get_user_mastery_summary).
        all_mastered = has_attempts and not effective_remedial

        return {
            "materials": recommended,
            "all_mastered": all_mastered,
        }
