"""
User notes / bookmarks table migration.

Additive only - creates a single dedicated table (user_notes) for the Learning
Path "Notes" feature. Does NOT touch any existing table.

A note bookmarks a SPECIFIC piece of learning content (not a whole page/file)
from one of three sources - Reading Materials, Practice Questions, or Chatbot
Discussions - and is tied to the authenticated user:

  - source_type   : 'material' | 'question' | 'chat'
  - source_id     : the specific content's stable reference within that source
                    (a material's URL, a question_id, or a chat message id).
                    Kept as TEXT because material URLs can be long.
  - source_ref    : JSONB structured reference used to open/return to the
                    original content (e.g. url/title/type, unit/bloom, or
                    conversation_id/role) - schema-flexible per source_type.
  - snapshot_text : the selected/snapshot content, stored so the note stays
                    understandable even if the source UI later changes.

Duplicate prevention: UNIQUE(user_id, source_type, source_id) - the same user
can't save the same specific content twice; this is what makes the
Save-to-Notes / Remove-from-Notes action a clean toggle.
"""

from config.database import execute_query


def create_user_notes_table():
    """Create the user_notes table if it doesn't exist."""
    query = """
    CREATE TABLE IF NOT EXISTS user_notes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        source_type VARCHAR(20) NOT NULL,
        source_id TEXT NOT NULL,
        title TEXT,
        snapshot_text TEXT NOT NULL,
        source_ref JSONB,
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE (user_id, source_type, source_id)
    );

    CREATE INDEX IF NOT EXISTS idx_user_notes_user_id ON user_notes(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_notes_user_type ON user_notes(user_id, source_type);
    CREATE INDEX IF NOT EXISTS idx_user_notes_created_at ON user_notes(created_at);
    """
    try:
        execute_query(query)
        print("✓ user_notes table created successfully or already exists")
        return True
    except Exception as e:
        print(f"✗ Failed to create user_notes table: {str(e)}")
        return False


def check_user_notes_table_exists():
    """Check whether the user_notes table exists."""
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables WHERE table_name = 'user_notes'
    );
    """
    try:
        result = execute_query(query, fetch=True)
        exists = result and result[0][0]
        status = "✓" if exists else "✗"
        print(f"{status} user_notes table exists: {exists}")
        return bool(exists)
    except Exception as e:
        print(f"✗ Failed to check user_notes table: {str(e)}")
        return False


if __name__ == "__main__":
    create_user_notes_table()
    check_user_notes_table_exists()
