"""
User free notes table migration.

Additive only - a single dedicated table (user_free_notes) for the
user-authored WYSIWYG notes on the Cue Questions ("Free Question" tab) and
Key Points ("Free Notes" tab) pages. Does NOT touch any existing table.

Unlike user_notes (a snapshot bookmarked FROM other content) and
user_reflections (answers to fixed configured questions), a free note is
purely user-authored rich text with no source to reference - just a category
so it renders on the right tab, and the HTML content itself.

  - category      : 'question' (Cue Questions -> Free Question) or
                    'key_points' (Key Points -> Free Notes) - which tab it
                    belongs to. Deliberately not source_type/source_id, since
                    there is no source content being bookmarked here.
  - content_html  : the rich-text content, as HTML produced by the WYSIWYG
                    editor (streamlit-quill).

A user can create any number of free notes per category; each is edited/
deleted independently (no uniqueness constraint - unlike user_notes, there is
no "duplicate of the same source" concept to prevent here).
"""

from config.database import execute_query


def create_user_free_notes_table():
    """Create the user_free_notes table if it doesn't exist."""
    query = """
    CREATE TABLE IF NOT EXISTS user_free_notes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        category VARCHAR(20) NOT NULL,
        content_html TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_user_free_notes_user_id ON user_free_notes(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_free_notes_user_category ON user_free_notes(user_id, category);
    """
    try:
        execute_query(query)
        print("✓ user_free_notes table created successfully or already exists")
        return True
    except Exception as e:
        print(f"✗ Failed to create user_free_notes table: {str(e)}")
        return False


def check_user_free_notes_table_exists():
    """Check whether the user_free_notes table exists."""
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables WHERE table_name = 'user_free_notes'
    );
    """
    try:
        result = execute_query(query, fetch=True)
        exists = result and result[0][0]
        status = "✓" if exists else "✗"
        print(f"{status} user_free_notes table exists: {exists}")
        return bool(exists)
    except Exception as e:
        print(f"✗ Failed to check user_free_notes table: {str(e)}")
        return False


if __name__ == "__main__":
    create_user_free_notes_table()
    check_user_free_notes_table_exists()
