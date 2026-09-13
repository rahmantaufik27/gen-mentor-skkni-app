"""
Adds material_id + material_title to unit_discussion_posts, so a discussion
thread can optionally be scoped to one specific reading material instead of
the whole unit - while staying anchored under unit_code, which stays
NOT NULL (verified: every Concept/material has exactly one parent Unit via
Neo4j's (Unit)-[:HAS_CONCEPT]->(Concept), so "per-material" is always a
child of "per-unit", never a sibling of it).

Additive only - two nullable columns on the existing table
(migrations/010_create_unit_discussions_table.py):

  - material_id    : the SAME stable identifier reading_materials.py's
                      _material_source_id() already uses for a material
                      with no DB id (its url, or "title|unit_code" as a
                      fallback) - so a discussion thread and a Notes
                      bookmark for the same material line up on the same
                      key without a new id scheme. NULL means "this post
                      belongs to the unit's general discussion", not to
                      any one material.
  - material_title : denormalized at post time, since materials live in
                      Neo4j (no queryable-by-id Postgres table to join
                      back to for a title at read time).
"""

from config.database import execute_query


def add_material_scope_columns():
    """Add material_id/material_title columns if they don't exist yet."""
    query = """
    ALTER TABLE unit_discussion_posts
    ADD COLUMN IF NOT EXISTS material_id VARCHAR(500),
    ADD COLUMN IF NOT EXISTS material_title VARCHAR(255);

    CREATE INDEX IF NOT EXISTS idx_unit_discussion_posts_material
        ON unit_discussion_posts(unit_code, material_id);
    """
    try:
        execute_query(query)
        print("✓ unit_discussion_posts.material_id/material_title added successfully or already exist")
        return True
    except Exception as e:
        print(f"✗ Failed to add material scope columns: {str(e)}")
        return False


def check_material_scope_columns_exist():
    """Check whether the material_id column exists (material_title is added alongside it)."""
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.columns
        WHERE table_name = 'unit_discussion_posts' AND column_name = 'material_id'
    );
    """
    try:
        result = execute_query(query, fetch=True)
        exists = result and result[0][0]
        status = "✓" if exists else "✗"
        print(f"{status} unit_discussion_posts.material_id exists: {exists}")
        return bool(exists)
    except Exception as e:
        print(f"✗ Failed to check material scope columns: {str(e)}")
        return False


if __name__ == "__main__":
    add_material_scope_columns()
    check_material_scope_columns_exist()
