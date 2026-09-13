"""
Performance migration: adds the indexes user_mastery_level and
quiz_attempt_details were missing on the live database.

Found during a 200-concurrent-user scalability audit: MasteryService's
core query (SELECT ... FROM user_mastery_level WHERE attempt_id = %s,
services/mastery_service.py) had no index to use on that column - only
the primary key (id) was indexed, confirmed by querying pg_indexes
directly against the live database. Every mastery summary lookup
(My Profile, Test, Practice, and especially the Peer Benchmark's
one-call-per-learner loop - services/learning_path_stats_service.py::
_peer_benchmark_stats) was therefore a full table scan. Unnoticeable at
today's row counts, but the single highest-impact, lowest-risk fix ahead
of any real concurrent load - purely additive, changes no existing data
or query results.

Also documents that this project's tracked migrations don't necessarily
match the live schema 1:1 (the live user_mastery_level table itself has
no CREATE TABLE migration in this repo at all - see app.py's note that
"the users/quiz schema already exists in the live database and is
managed manually") - this migration only adds indexes, so it's safe to
run regardless of how the table itself was created.
"""

from config.database import execute_query


_INDEXES = [
    ("idx_user_mastery_level_attempt_id",
     "CREATE INDEX IF NOT EXISTS idx_user_mastery_level_attempt_id ON user_mastery_level(attempt_id);"),
    ("idx_user_mastery_level_user_id",
     "CREATE INDEX IF NOT EXISTS idx_user_mastery_level_user_id ON user_mastery_level(user_id);"),
    # NOTE: quiz_attempt_details' FK column to quiz_attempts is actually
    # named "attempt_id" on the live table (verified directly against
    # information_schema.columns) - migrations/002_create_quiz_tables.py's
    # own comment names it "quiz_attempt_id", which doesn't exist; another
    # instance of the tracked migrations not matching the live schema.
    ("idx_quiz_attempt_details_attempt_id",
     "CREATE INDEX IF NOT EXISTS idx_quiz_attempt_details_attempt_id ON quiz_attempt_details(attempt_id);"),
]


def add_mastery_query_indexes():
    """Add the missing indexes if they don't exist yet - one statement at a
    time, so one failing (e.g. a column name that turns out not to match
    the live schema) doesn't roll back the others in the same batch."""
    all_ok = True
    for name, statement in _INDEXES:
        try:
            execute_query(statement)
            print(f"✓ {name} added successfully or already exists")
        except Exception as e:
            all_ok = False
            print(f"✗ Failed to add {name}: {str(e)}")
    return all_ok


def check_mastery_query_indexes_exist():
    """Check whether the indexes exist."""
    query = "SELECT indexname FROM pg_indexes WHERE indexname = ANY(%s);"
    expected = {name for name, _ in _INDEXES}
    try:
        result = execute_query(query, (list(expected),), fetch=True)
        found = {row[0] for row in (result or [])}
        for name in sorted(expected):
            status = "✓" if name in found else "✗"
            print(f"{status} {name} exists: {name in found}")
        return found == expected
    except Exception as e:
        print(f"✗ Failed to check mastery query indexes: {str(e)}")
        return False


if __name__ == "__main__":
    add_mastery_query_indexes()
    check_mastery_query_indexes_exist()
