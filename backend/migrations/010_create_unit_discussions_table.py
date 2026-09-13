"""
Unit discussion posts table migration.

Additive only - a single dedicated table (unit_discussion_posts) for a
peer-to-peer Q&A forum, one thread per SKKNI unit (Learning Path ->
Discussion). Does NOT touch any existing table.

Deliberately flat: top-level posts plus at most one level of replies via
parent_post_id (self-referencing FK, ON DELETE CASCADE so deleting a
top-level post also removes its replies) - no deep threading, this is meant
for quick peer help, not a full-blown forum.

unit_code is a plain VARCHAR, not a foreign key - unit master data lives in
the Neo4j knowledge graph / data/knowledge_target.json, not in a Postgres
table, matching the existing convention (user_mastery_level.unit_code,
practice_attempt_units.unit_code, etc. are all plain VARCHAR too).

Posts are NOT anonymous - unlike Free Notes/Reflection (private per-user
data), a discussion post is inherently public to every learner, so the
service joins to users.full_name at read time (not denormalized here)
to show who wrote it.
"""

from config.database import execute_query


def create_unit_discussion_posts_table():
    """Create the unit_discussion_posts table if it doesn't exist."""
    query = """
    CREATE TABLE IF NOT EXISTS unit_discussion_posts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        unit_code VARCHAR(50) NOT NULL,
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        parent_post_id UUID REFERENCES unit_discussion_posts(id) ON DELETE CASCADE,
        body TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_unit_discussion_posts_unit_code ON unit_discussion_posts(unit_code);
    CREATE INDEX IF NOT EXISTS idx_unit_discussion_posts_parent ON unit_discussion_posts(parent_post_id);
    CREATE INDEX IF NOT EXISTS idx_unit_discussion_posts_user_id ON unit_discussion_posts(user_id);
    """
    try:
        execute_query(query)
        print("✓ unit_discussion_posts table created successfully or already exists")
        return True
    except Exception as e:
        print(f"✗ Failed to create unit_discussion_posts table: {str(e)}")
        return False


def check_unit_discussion_posts_table_exists():
    """Check whether the unit_discussion_posts table exists."""
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables WHERE table_name = 'unit_discussion_posts'
    );
    """
    try:
        result = execute_query(query, fetch=True)
        exists = result and result[0][0]
        status = "✓" if exists else "✗"
        print(f"{status} unit_discussion_posts table exists: {exists}")
        return bool(exists)
    except Exception as e:
        print(f"✗ Failed to check unit_discussion_posts table: {str(e)}")
        return False


if __name__ == "__main__":
    create_unit_discussion_posts_table()
    check_unit_discussion_posts_table_exists()
