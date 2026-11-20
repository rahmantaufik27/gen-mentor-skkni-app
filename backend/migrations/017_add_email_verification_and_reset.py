"""
Email verification + password reset migration.

Additive only:
  - users.email_verified : BOOLEAN NOT NULL DEFAULT TRUE. The default is
    TRUE on purpose - every account that already exists when this runs is
    treated as verified, so nobody is locked out. New registrations set it
    to FALSE explicitly (only while email sending is enabled, see
    config/mail.py), and it flips to TRUE when the emailed link is opened.
  - auth_tokens : one-time links for 'verify' (confirm email) and 'reset'
    (password reset). Only the SHA-256 hash of a token is stored, so a
    database leak can't be turned into working links.
"""

from config.database import execute_query


def migrate():
    query = """
    ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT TRUE;

    CREATE TABLE IF NOT EXISTS auth_tokens (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        purpose VARCHAR(20) NOT NULL,
        token_hash CHAR(64) NOT NULL UNIQUE,
        expires_at TIMESTAMP NOT NULL,
        used_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_auth_tokens_user_purpose ON auth_tokens(user_id, purpose);
    """
    try:
        execute_query(query)
        print("OK: users.email_verified and auth_tokens are in place")
        return True
    except Exception as e:
        print(f"FAILED: {str(e)}")
        return False


if __name__ == "__main__":
    migrate()
