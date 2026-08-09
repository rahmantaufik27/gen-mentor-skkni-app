"""
User activity events table migration.

Additive only - does not touch users/quiz_attempts/quiz_attempt_details/
user_mastery_level/practice_attempts. Backs the lightweight Learning Path
statistics APIs (see services/learning_path_stats_service.py): a single,
generic append-only event log keyed by (user_id, activity_type).

Deliberately generic: each metric that needs an "activity count" or a "latest
interaction timestamp" (materials opened, chatbot prompts, and any future one)
is just another activity_type - no schema change is needed to add a new metric.
The optional metadata JSONB carries per-event detail (e.g. a material's unit
code) for metrics that want it later, without altering this table.
"""

from config.database import execute_query


def create_user_activity_table():
    """Create the user_activity table if it doesn't exist."""

    user_activity_query = """
    CREATE TABLE IF NOT EXISTS user_activity (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        activity_type VARCHAR(50) NOT NULL,
        metadata JSONB,
        occurred_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_user_activity_user_id ON user_activity(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_activity_type ON user_activity(user_id, activity_type);
    CREATE INDEX IF NOT EXISTS idx_user_activity_occurred_at ON user_activity(occurred_at);
    """

    try:
        execute_query(user_activity_query)
        print("✓ user_activity table created successfully or already exists")
        return True
    except Exception as e:
        print(f"✗ Failed to create user_activity table: {str(e)}")
        return False


def check_user_activity_table_exists():
    """Check if the user_activity table exists."""
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables
        WHERE table_name = 'user_activity'
    );
    """
    try:
        result = execute_query(query, fetch=True)
        exists = result and result[0][0]
        status = "✓" if exists else "✗"
        print(f"{status} user_activity table exists: {exists}")
        return bool(exists)
    except Exception as e:
        print(f"✗ Failed to check user_activity table: {str(e)}")
        return False


if __name__ == "__main__":
    create_user_activity_table()
    check_user_activity_table_exists()
