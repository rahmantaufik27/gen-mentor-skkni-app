"""
Practice attempts tables migration.

Additive only - does not touch users/quiz_attempts/quiz_attempt_details/
user_mastery_level. Backs the Practice Analytics section of the My Profile
dashboard (total sessions, per-unit Knowledge Level progression). Written by
PracticeService.complete_practice() as a best-effort session summary; never
read by Test/mastery logic, so Test remains the sole source of mastery truth.
"""

from config.database import execute_query


def create_practice_attempts_tables():
    """Create practice_attempts / practice_attempt_units tables if they don't exist."""

    practice_attempts_query = """
    CREATE TABLE IF NOT EXISTS practice_attempts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        total_questions INT NOT NULL,
        correct_answers INT DEFAULT 0,
        total_score INT DEFAULT 0,
        max_possible_score INT DEFAULT 0,
        completed_at TIMESTAMP DEFAULT NOW(),
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_practice_attempts_user_id ON practice_attempts(user_id);
    CREATE INDEX IF NOT EXISTS idx_practice_attempts_completed_at ON practice_attempts(completed_at);
    """

    # One row per unit covered in the session, with the highest Bloom level
    # answered correctly for that unit this session (a snapshot for the
    # progression chart - not the same thing as user_mastery_level.unit_mastery_level).
    practice_attempt_units_query = """
    CREATE TABLE IF NOT EXISTS practice_attempt_units (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        practice_attempt_id UUID NOT NULL REFERENCES practice_attempts(id) ON DELETE CASCADE,
        unit_code VARCHAR(50) NOT NULL,
        unit_mastery_level VARCHAR(3) NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_practice_attempt_units_attempt_id ON practice_attempt_units(practice_attempt_id);
    CREATE INDEX IF NOT EXISTS idx_practice_attempt_units_unit_code ON practice_attempt_units(unit_code);
    """

    try:
        execute_query(practice_attempts_query)
        print("✓ practice_attempts table created successfully or already exists")

        execute_query(practice_attempt_units_query)
        print("✓ practice_attempt_units table created successfully or already exists")

        return True
    except Exception as e:
        print(f"✗ Failed to create practice attempts tables: {str(e)}")
        return False


def check_practice_attempts_tables_exist():
    """Check if practice_attempts / practice_attempt_units tables exist."""
    tables_to_check = ["practice_attempts", "practice_attempt_units"]

    all_exist = True
    for table_name in tables_to_check:
        query = f"""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = '{table_name}'
        );
        """
        try:
            result = execute_query(query, fetch=True)
            exists = result and result[0][0]
            status = "✓" if exists else "✗"
            print(f"{status} {table_name} table exists: {exists}")
            if not exists:
                all_exist = False
        except Exception as e:
            print(f"✗ Failed to check {table_name} table: {str(e)}")
            all_exist = False

    return all_exist


if __name__ == "__main__":
    create_practice_attempts_tables()
    check_practice_attempts_tables_exist()
