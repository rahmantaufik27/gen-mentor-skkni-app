"""
Adds is_best_answer to unit_discussion_posts.

Additive only - a single nullable-with-default column on the existing
table (migrations/010_create_unit_discussions_table.py), nothing else
changes. Only ever TRUE on a reply (parent_post_id IS NOT NULL); the
service enforces "at most one best answer per parent post" with a single
UPDATE (see DiscussionService.set_best_answer), not a DB constraint, since
Postgres has no native "unique per group, only when true" constraint
without a partial unique index - not worth the extra migration complexity
for a boolean the app already keeps consistent on every write.
"""

from config.database import execute_query


def add_best_answer_column():
    """Add the is_best_answer column if it doesn't exist yet."""
    query = """
    ALTER TABLE unit_discussion_posts
    ADD COLUMN IF NOT EXISTS is_best_answer BOOLEAN NOT NULL DEFAULT FALSE;
    """
    try:
        execute_query(query)
        print("✓ unit_discussion_posts.is_best_answer added successfully or already exists")
        return True
    except Exception as e:
        print(f"✗ Failed to add is_best_answer column: {str(e)}")
        return False


def check_best_answer_column_exists():
    """Check whether the is_best_answer column exists."""
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.columns
        WHERE table_name = 'unit_discussion_posts' AND column_name = 'is_best_answer'
    );
    """
    try:
        result = execute_query(query, fetch=True)
        exists = result and result[0][0]
        status = "✓" if exists else "✗"
        print(f"{status} unit_discussion_posts.is_best_answer exists: {exists}")
        return bool(exists)
    except Exception as e:
        print(f"✗ Failed to check is_best_answer column: {str(e)}")
        return False


if __name__ == "__main__":
    add_best_answer_column()
    check_best_answer_column_exists()
