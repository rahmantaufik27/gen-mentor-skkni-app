#!/usr/bin/env python
"""Check database schema for quiz tables."""

from config.database import execute_query

# Get schema for quiz_attempts
print("=== quiz_attempts ===")
result = execute_query("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'quiz_attempts'
    ORDER BY ordinal_position
""", fetch=True)
if result:
    for row in result:
        print(f"{row[0]:20} {row[1]:15} {row[2]}")
else:
    print("No columns found")

print("\n=== quiz_attempt_details ===")
result = execute_query("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_name = 'quiz_attempt_details'
    ORDER BY ordinal_position
""", fetch=True)
if result:
    for row in result:
        print(f"{row[0]:20} {row[1]:15} {row[2]}")
else:
    print("No columns found")

print("\n=== Sample records ===")
print("quiz_attempts:")
result = execute_query("SELECT * FROM quiz_attempts LIMIT 5", fetch=True)
print(result if result else "Empty table")

print("\nquiz_attempt_details:")
result = execute_query("SELECT * FROM quiz_attempt_details LIMIT 5", fetch=True)
print(result if result else "Empty table")
