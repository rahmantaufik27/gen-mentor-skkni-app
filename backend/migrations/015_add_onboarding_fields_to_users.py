"""
Adds onboarding fields to users.

Additive only - three columns on the existing users table
(migrations/001_create_users_table.py):
- onboarding_completed: whether the user has been through the onboarding
  wizard (frontend/pages/onboarding.py) at least once - main.py routes a
  fresh login there instead of straight to My Profile while this is false.
- target_role / target_level: the SKKNI role and level the learner picked
  as their goal in onboarding's "Choose Your Path" step (see
  frontend/data/skkni_ladder.py). Purely informational today (shown back
  on the Ready screen / My Profile), not used for any content gating.
"""

from config.database import execute_query


def add_onboarding_columns():
    """Add the onboarding columns if they don't exist yet."""
    query = """
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS target_role VARCHAR(255),
    ADD COLUMN IF NOT EXISTS target_level SMALLINT;
    """
    try:
        execute_query(query)
        print("✓ users onboarding columns added successfully or already exist")
        return True
    except Exception as e:
        print(f"✗ Failed to add onboarding columns: {str(e)}")
        return False


def check_onboarding_columns_exist():
    """Check whether the onboarding columns exist."""
    query = """
    SELECT column_name FROM information_schema.columns
    WHERE table_name = 'users'
      AND column_name IN ('onboarding_completed', 'target_role', 'target_level');
    """
    try:
        result = execute_query(query, fetch=True)
        found = {row[0] for row in result} if result else set()
        for col in ("onboarding_completed", "target_role", "target_level"):
            status = "✓" if col in found else "✗"
            print(f"{status} users.{col} exists: {col in found}")
        return len(found) == 3
    except Exception as e:
        print(f"✗ Failed to check onboarding columns: {str(e)}")
        return False


if __name__ == "__main__":
    add_onboarding_columns()
    check_onboarding_columns_exist()
