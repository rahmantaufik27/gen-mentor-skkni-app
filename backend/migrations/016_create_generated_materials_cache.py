"""
Generated-materials cache migration.

Additive only - creates two dedicated tables that cache the LLM output of
on-demand learning-material generation (materials_service.list_subtopics /
generate_subtopic_material). Does NOT touch any existing table.

Generated content is NOT personalized per learner (same unit + same
subtopic index always produces the same prompt), so the cache is shared
across all users rather than keyed by user_id - this keeps storage bounded
by (number of units x subtopics per unit) instead of growing with the
number of users who happen to generate the same material.

  - generated_subtopic_lists   : caches list_subtopics(unit_code) so the
                                  lightweight "list subtopic titles" LLM
                                  call also only ever runs once per unit.
  - generated_subtopic_materials : caches generate_subtopic_material(unit_code,
                                  subtopic_index) - the actual learning
                                  material body.

Lookup is always "check cache first, call LLM + write-through only on a
miss" - see MaterialsService._get_cached_subtopics /
_get_cached_subtopic_material in services/materials_service.py.
"""

from config.database import execute_query


def create_generated_materials_cache_tables():
    """Create the generated-materials cache tables if they don't exist."""
    query = """
    CREATE TABLE IF NOT EXISTS generated_subtopic_lists (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        unit_code VARCHAR(50) NOT NULL,
        subtopics JSONB NOT NULL,
        provider VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (unit_code)
    );

    CREATE TABLE IF NOT EXISTS generated_subtopic_materials (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        unit_code VARCHAR(50) NOT NULL,
        subtopic_index INTEGER NOT NULL,
        subtopic_title TEXT,
        material TEXT NOT NULL,
        provider VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (unit_code, subtopic_index)
    );

    CREATE INDEX IF NOT EXISTS idx_generated_subtopic_materials_unit
        ON generated_subtopic_materials(unit_code);
    """
    try:
        execute_query(query)
        print("✓ generated_subtopic_lists / generated_subtopic_materials tables created successfully or already exist")
        return True
    except Exception as e:
        print(f"✗ Failed to create generated-materials cache tables: {str(e)}")
        return False


def check_generated_materials_cache_tables_exist():
    """Check whether both cache tables exist."""
    query = """
    SELECT table_name FROM information_schema.tables
    WHERE table_name IN ('generated_subtopic_lists', 'generated_subtopic_materials');
    """
    try:
        result = execute_query(query, fetch=True)
        found = {row[0] for row in (result or [])}
        for name in ("generated_subtopic_lists", "generated_subtopic_materials"):
            status = "✓" if name in found else "✗"
            print(f"{status} {name} table exists: {name in found}")
        return {"generated_subtopic_lists", "generated_subtopic_materials"} <= found
    except Exception as e:
        print(f"✗ Failed to check generated-materials cache tables: {str(e)}")
        return False


if __name__ == "__main__":
    create_generated_materials_cache_tables()
    check_generated_materials_cache_tables_exist()
