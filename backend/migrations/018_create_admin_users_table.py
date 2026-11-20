"""
Admin accounts table migration.

Replaces the admin email/password that used to be hardcoded in
services/admin_auth_service.py. Passwords are stored as bcrypt hashes, the
same way learner passwords are.

Create the first admin on a fresh database with:
    python -m migrations.018_create_admin_users_table <email> <password> [full name]
Running it with no arguments only creates the table.
"""

import sys

import bcrypt

from config.database import execute_query


def migrate() -> bool:
    query = """
    CREATE TABLE IF NOT EXISTS admin_users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email VARCHAR(255) UNIQUE NOT NULL,
        full_name VARCHAR(255) NOT NULL DEFAULT 'Admin',
        password_hash TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMP DEFAULT NOW(),
        last_login_at TIMESTAMP
    );
    """
    try:
        execute_query(query)
        print("OK: admin_users table is in place")
        return True
    except Exception as e:
        print(f"FAILED: {str(e)}")
        return False


def create_admin(email: str, password: str, full_name: str = "Admin") -> bool:
    """Add an admin account; leaves an existing account with that email untouched."""
    if len(password) < 8:
        print("FAILED: password must be at least 8 characters")
        return False
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
    execute_query(
        """
        INSERT INTO admin_users (email, full_name, password_hash)
        VALUES (%s, %s, %s)
        ON CONFLICT (email) DO NOTHING
        """,
        (email.strip().lower(), full_name, password_hash),
    )
    print(f"OK: admin account ready for {email.strip().lower()}")
    return True


if __name__ == "__main__":
    if migrate() and len(sys.argv) >= 3:
        create_admin(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "Admin")
