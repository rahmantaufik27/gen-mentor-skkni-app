"""
Dedicated Neo4j module: owns the driver connection, all Cypher queries, and
synchronization from PostgreSQL (the source of truth) into the Neo4j
knowledge graph used for recommendations.

This connects to an EXISTING knowledge graph (instance "genq_skkni" in Neo4j
Desktop, database "neo4j") that already contains the SKKNI unit/material/
question structure:

    (:Unit {kode, title})
      -[:HAS_CONCEPT]->(:Concept {text})            <- reading materials
      -[:HAS_EVALUATION]->(:Evaluation {soal, bloom_level, jawaban})  <- questions
           -[:HAS_OPTION]->(:Option {text})
           -[:HAS_CORRECT_ANSWER]->(:Answer {text})
           -[:HAS_LEVEL]->(:Level {name})

This module does NOT create parallel Material/Question nodes - it reads
Concept/Evaluation directly, and adds only what doesn't already exist:
User nodes and the (User)-[:MASTERY]->(Unit) relationship.

Design notes:
- Neo4j stores ONLY the current knowledge graph for recommendations.
  PostgreSQL remains the source of truth for users, quiz attempts, and
  history - nothing here is ever read back into Postgres.
- Every write uses MERGE so re-running a sync is always safe (no duplicate
  nodes/relationships).
- Every method degrades gracefully: if Neo4j is unreachable or a query
  fails, it's logged and a safe default ([]/False) is returned instead of
  raising, so a Neo4j outage can never break registration or the quiz flow
  (both remain fully backed by PostgreSQL).
- Every query and, for recommendation queries, the returned recommendations
  are logged to logs/neo4j.log for debugging/verification (see _run_query).
"""

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from config.neo4j_config import Neo4jConfig

BLOOM_LEVELS = ["C1", "C2", "C3", "C4", "C5", "C6"]

# Parses a Concept.text value like:
#   "Pertemuan 01 [presentation] - https://drive.google.com/file/d/.../view"
# into (title, type, url).
_CONCEPT_TEXT_RE = re.compile(r"^(?P<title>.*?)\s*\[(?P<type>[^\]]*)\]\s*-\s*(?P<url>\S+)\s*$")


def _bloom_rank(level: Optional[str]) -> int:
    """Ordinal rank of a Bloom level (C1=1 ... C6=6); 0 if unset/unrecognized."""
    if not level:
        return 0
    try:
        return BLOOM_LEVELS.index(level.upper()) + 1
    except ValueError:
        return 0


def _parse_concept_text(text: str) -> Dict[str, str]:
    """Split a Concept node's free-text field into title/type/url."""
    match = _CONCEPT_TEXT_RE.match(text or "")
    if match:
        return {"title": match.group("title"), "type": match.group("type"), "url": match.group("url")}
    return {"title": text or "", "type": "", "url": ""}


def _build_logger() -> logging.Logger:
    """Dedicated logger writing to backend/logs/neo4j.log (rotated at 2MB, 3 backups)."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    log_dir = os.path.join(backend_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger("neo4j_service")
    logger.setLevel(logging.INFO)
    if not logger.handlers:  # avoid duplicate handlers if the module is reloaded
        handler = RotatingFileHandler(
            os.path.join(log_dir, "neo4j.log"), maxBytes=2_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
    return logger


logger = _build_logger()


class Neo4jService:
    """Owns the Neo4j driver, query execution/logging, and sync/recommendation queries."""

    def __init__(self, config: Optional[Neo4jConfig] = None):
        self._driver = None  # created lazily, reused for the life of the process
        self._params = None
        try:
            self._params = (config or Neo4jConfig()).get_connection_params()
        except Exception as e:
            # Missing/invalid neo4j.ini must not take down the app - Postgres-backed
            # features (auth, quiz, mastery) keep working; Neo4j sync just no-ops.
            logger.warning("Neo4j config unavailable, integration disabled: %s", str(e))

    def _get_driver(self):
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self._params["uri"], auth=(self._params["user"], self._params["password"])
            )
        return self._driver

    def close(self):
        if self._driver is not None:
            self._driver.close()
            self._driver = None

    def _run_query(self, cypher: str, params: Optional[Dict] = None, purpose: str = "") -> List[Dict]:
        """
        Execute a Cypher query against the configured database, logging the
        query/params and the result. Never raises - returns [] on any error
        (including a missing config) so callers can always degrade gracefully.
        """
        if self._params is None:
            return []

        params = params or {}
        single_line_cypher = " ".join(cypher.split())
        try:
            driver = self._get_driver()
            with driver.session(database=self._params["database"]) as session:
                result = session.run(cypher, params)
                records = [record.data() for record in result]
            logger.info("[%s] query=%s params=%s -> %d record(s)", purpose, single_line_cypher, params, len(records))
            if purpose.startswith("recommend"):
                logger.info("[%s] recommendations=%s", purpose, records)
            return records
        except (ServiceUnavailable, Neo4jError, Exception) as e:
            logger.warning("[%s] query failed: %s | query=%s params=%s", purpose, str(e), single_line_cypher, params)
            return []

    # ------------------------------------------------------------------
    # Sync: PostgreSQL (source of truth) -> Neo4j (knowledge graph)
    # ------------------------------------------------------------------

    def sync_user(self, user_id: str, full_name: str = "", email: str = "") -> bool:
        """Create the User node if it doesn't exist yet (requirement: on registration)."""
        records = self._run_query(
            """
            MERGE (u:User {id: $user_id})
            ON CREATE SET u.full_name = $full_name, u.email = $email, u.created_at = datetime()
            ON MATCH SET u.full_name = $full_name, u.email = $email
            RETURN u.id AS id
            """,
            {"user_id": user_id, "full_name": full_name, "email": email},
            purpose="sync_user",
        )
        return len(records) > 0

    def sync_mastery(
        self, user_id: str, unit_code: str, knowledge_level: Optional[str], mastery_status: str,
        target_level: Optional[str] = None,
    ) -> bool:
        """
        Create/update (User)-[:MASTERY]->(Unit) after a quiz attempt.
        Uses MERGE on the relationship so re-syncing never creates duplicates -
        it just updates the existing relationship's properties.

        Args:
            unit_code: the FULL unit code (e.g. 'J.620100.005.02'), matching
                the existing Unit.kode property in the knowledge graph -
                NOT the 3-segment code used internally by Postgres.
        """
        records = self._run_query(
            """
            MERGE (u:User {id: $user_id})
            MERGE (unit:Unit {kode: $unit_code})
            MERGE (u)-[m:MASTERY]->(unit)
            SET m.knowledge_level = $knowledge_level,
                m.mastery_status = $mastery_status,
                m.target_level = $target_level,
                m.updated_at = datetime()
            RETURN m.knowledge_level AS knowledge_level
            """,
            {
                "user_id": user_id,
                "unit_code": unit_code,
                "knowledge_level": knowledge_level,
                "mastery_status": mastery_status,
                "target_level": target_level,
            },
            purpose="sync_mastery",
        )
        return len(records) > 0

    # ------------------------------------------------------------------
    # Recommendations (read-only, consumed by MaterialsService/QuizService)
    # ------------------------------------------------------------------

    def get_all_materials(self) -> List[Dict]:
        """All reading materials (Concept nodes) in the graph, for the 'All Materials' browse view."""
        records = self._run_query(
            """
            MATCH (unit:Unit)-[:HAS_CONCEPT]->(c:Concept)
            RETURN c.text AS text, unit.kode AS unit_code
            ORDER BY unit.kode, c.text
            """,
            purpose="list_materials",
        )
        materials = []
        for r in records:
            parsed = _parse_concept_text(r.get("text"))
            materials.append({**parsed, "unit_code": r.get("unit_code")})
        return materials

    def get_recommended_materials(self, user_id: str) -> List[Dict]:
        """
        Materials (Concept nodes) for units the user's MASTERY relationship
        marks Remedial, prioritized by lowest knowledge_level first
        (furthest behind).
        """
        records = self._run_query(
            """
            MATCH (u:User {id: $user_id})-[m:MASTERY]->(unit:Unit)-[:HAS_CONCEPT]->(c:Concept)
            WHERE m.mastery_status = 'Remedial'
            RETURN c.text AS text, unit.kode AS unit_code,
                   m.mastery_status AS mastery_status, m.knowledge_level AS unit_mastery_level,
                   m.target_level AS target_level
            """,
            {"user_id": user_id},
            purpose="recommend_materials",
        )
        materials = []
        for r in records:
            parsed = _parse_concept_text(r.get("text"))
            materials.append({
                **parsed,
                "unit_code": r.get("unit_code"),
                "mastery_status": r.get("mastery_status"),
                "unit_mastery_level": r.get("unit_mastery_level"),
                "target_level": r.get("target_level"),
            })
        materials.sort(key=lambda m: (_bloom_rank(m.get("unit_mastery_level")), m.get("unit_code") or ""))
        return materials

    def get_recommended_questions(self, user_id: str) -> List[Dict]:
        """
        Questions (Evaluation nodes) for Remedial units at the user's current
        knowledge_level for that unit (or C1 if the unit has never been
        attempted). Options are included as plain text; which option is
        correct is intentionally omitted from the response.
        """
        records = self._run_query(
            """
            MATCH (u:User {id: $user_id})-[m:MASTERY]->(unit:Unit)-[:HAS_EVALUATION]->(e:Evaluation)
            WHERE m.mastery_status = 'Remedial' AND e.bloom_level = coalesce(m.knowledge_level, 'C1')
            OPTIONAL MATCH (e)-[:HAS_OPTION]->(o:Option)
            WITH u, unit, m, e, collect(o.text) AS options
            RETURN elementId(e) AS question_id, e.soal AS question_text, e.bloom_level AS bloom_level,
                   options, unit.kode AS unit_code, m.mastery_status AS mastery_status,
                   m.target_level AS target_level
            """,
            {"user_id": user_id},
            purpose="recommend_questions",
        )
        records.sort(key=lambda r: (_bloom_rank(r.get("bloom_level")), r.get("unit_code") or ""))
        return records


_singleton: Optional[Neo4jService] = None


def get_neo4j_service() -> Neo4jService:
    """Process-wide singleton so the app reuses one Neo4j driver/connection pool."""
    global _singleton
    if _singleton is None:
        _singleton = Neo4jService()
    return _singleton
