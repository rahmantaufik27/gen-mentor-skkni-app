"""
User reflections table migration.

Additive only - a single dedicated table (user_reflections) for the Learning
Reflection feature (Learning Path -> Notes -> Learning Reflection). Does NOT
touch any existing table.

Each row is one user's answer to one configured reflection question:

  - question_key : STABLE key from data/reflection_questions.json. The question
                   TEXT is never stored here (questions may change dynamically);
                   only the key is, so answers stay associated even if wording
                   changes.
  - answer_text  : free-text answers.
  - answer_number: numeric answers (e.g. the 1-5 Motivation Rating).
                   A question uses one column or the other per its config type.

Duplicate prevention / edit-in-place: UNIQUE(user_id, question_key) - one answer
per user per question, upserted on edit. Per-user isolation is enforced by every
query being scoped to user_id (see NotesService for the same convention).
"""

from config.database import execute_query


def create_user_reflections_table():
    """Create the user_reflections table if it doesn't exist."""
    query = """
    CREATE TABLE IF NOT EXISTS user_reflections (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        question_key VARCHAR(64) NOT NULL,
        answer_text TEXT,
        answer_number INTEGER,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, question_key)
    );

    CREATE INDEX IF NOT EXISTS idx_user_reflections_user_id ON user_reflections(user_id);
    """
    try:
        execute_query(query)
        print("✓ user_reflections table created successfully or already exists")
        return True
    except Exception as e:
        print(f"✗ Failed to create user_reflections table: {str(e)}")
        return False


def check_user_reflections_table_exists():
    """Check whether the user_reflections table exists."""
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables WHERE table_name = 'user_reflections'
    );
    """
    try:
        result = execute_query(query, fetch=True)
        exists = result and result[0][0]
        status = "✓" if exists else "✗"
        print(f"{status} user_reflections table exists: {exists}")
        return bool(exists)
    except Exception as e:
        print(f"✗ Failed to check user_reflections table: {str(e)}")
        return False


if __name__ == "__main__":
    create_user_reflections_table()
    check_user_reflections_table_exists()
