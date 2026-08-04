"""
Migration: add inference_method column to users table.

Documents a schema change already applied manually to the live database
(this project's migrations are not auto-run - see app.py). Records each
user's mastery-inference engine preference ('DBN' or 'Manual'), defaulting
to 'DBN' for every newly registered user.
"""

from config.database import execute_query


def add_inference_method_column():
    """Add inference_method column to users table if it doesn't exist."""
    query = """
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS inference_method VARCHAR(20) NOT NULL DEFAULT 'DBN';
    """
    try:
        execute_query(query)
        print("✓ inference_method column added to users table")
        return True
    except Exception as e:
        print(f"✗ Failed to add inference_method column: {str(e)}")
        return False


def check_inference_method_column_exists():
    """Check if the inference_method column exists on users."""
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'inference_method'
    );
    """
    try:
        result = execute_query(query, fetch=True)
        if result and result[0][0]:
            print("✓ inference_method column exists")
            return True
        else:
            print("✗ inference_method column does not exist")
            return False
    except Exception as e:
        print(f"✗ Failed to check inference_method column: {str(e)}")
        return False
