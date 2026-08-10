"""
Add test_stage to quiz_attempts (Pre-Test / Post-Test progression).

Additive, backwards-compatible: a nullable-defaulted VARCHAR column so every
existing attempt is treated as a Pre-Test ('pre'). The Test is now a TWO-stage
progression:

  - 'pre'  : the initial Placement / Pre-Test (taken once, first).
  - 'post' : the Post-Test, unlocked only after the learner has cleared every
             Practice recommendation (all units at target - see
             MasteryService/QuizService for the gating rule).

No other quiz table changes: per-unit results still live in
quiz_attempt_details / user_mastery_level keyed by attempt_id, so each stage's
attempt keeps its own independent per-unit mastery snapshot for free.
"""

from config.database import execute_query


def add_test_stage_column():
    """Add the test_stage column to quiz_attempts if it doesn't exist."""
    query = """
    ALTER TABLE quiz_attempts
    ADD COLUMN IF NOT EXISTS test_stage VARCHAR(10) NOT NULL DEFAULT 'pre';

    CREATE INDEX IF NOT EXISTS idx_quiz_attempts_test_stage
    ON quiz_attempts(user_id, test_stage);
    """
    try:
        execute_query(query)
        print("✓ quiz_attempts.test_stage column added successfully or already exists")
        return True
    except Exception as e:
        print(f"✗ Failed to add test_stage column: {str(e)}")
        return False


def check_test_stage_column_exists():
    """Check whether quiz_attempts.test_stage exists."""
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.columns
        WHERE table_name = 'quiz_attempts' AND column_name = 'test_stage'
    );
    """
    try:
        result = execute_query(query, fetch=True)
        exists = result and result[0][0]
        status = "✓" if exists else "✗"
        print(f"{status} quiz_attempts.test_stage column exists: {exists}")
        return bool(exists)
    except Exception as e:
        print(f"✗ Failed to check test_stage column: {str(e)}")
        return False


if __name__ == "__main__":
    add_test_stage_column()
    check_test_stage_column_exists()
