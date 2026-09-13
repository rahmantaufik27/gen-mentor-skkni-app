"""
Adds profile_photo_path to users.

Additive only - a single nullable column on the existing users table
(migrations/001_create_users_table.py). Stores just the saved filename
(e.g. "<user_id>.jpg", see AuthController.upload_profile_photo), not a
full path, so the storage location (backend/storage/profile_photos/) can
move without a data migration.
"""

from config.database import execute_query


def add_profile_photo_column():
    """Add the profile_photo_path column if it doesn't exist yet."""
    query = """
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS profile_photo_path VARCHAR(255);
    """
    try:
        execute_query(query)
        print("✓ users.profile_photo_path added successfully or already exists")
        return True
    except Exception as e:
        print(f"✗ Failed to add profile_photo_path column: {str(e)}")
        return False


def check_profile_photo_column_exists():
    """Check whether the profile_photo_path column exists."""
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.columns
        WHERE table_name = 'users' AND column_name = 'profile_photo_path'
    );
    """
    try:
        result = execute_query(query, fetch=True)
        exists = result and result[0][0]
        status = "✓" if exists else "✗"
        print(f"{status} users.profile_photo_path exists: {exists}")
        return bool(exists)
    except Exception as e:
        print(f"✗ Failed to check profile_photo_path column: {str(e)}")
        return False


if __name__ == "__main__":
    add_profile_photo_column()
    check_profile_photo_column_exists()
