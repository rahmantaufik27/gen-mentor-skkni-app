#!/usr/bin/env python3
"""Check if required database tables exist."""

from config.database import execute_query
import sys

try:
    result = execute_query(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'",
        fetch=True
    )
    tables = [row[0] for row in result]
    print("Tables in database:", tables)
    
    if 'quiz_attempts' in tables:
        print("✓ quiz_attempts exists")
    else:
        print("✗ quiz_attempts MISSING")
    
    if 'quiz_attempt_details' in tables:
        print("✓ quiz_attempt_details exists")
    else:
        print("✗ quiz_attempt_details MISSING")
    
    if 'user_mastery' in tables:
        print("✓ user_mastery exists")
    else:
        print("✗ user_mastery MISSING")
        
except Exception as e:
    print(f"Error checking tables: {e}")
    sys.exit(1)
