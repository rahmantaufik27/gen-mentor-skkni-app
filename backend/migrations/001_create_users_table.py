"""User table migration."""

from config.database import execute_query


def create_users_table():
    """Create users table if it doesn't exist."""
    query = """
    CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        full_name VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    
    -- Create an index on email for faster lookups
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    """
    
    try:
        execute_query(query)
        print("✓ Users table created successfully or already exists")
        return True
    except Exception as e:
        print(f"✗ Failed to create users table: {str(e)}")
        return False


def check_users_table_exists():
    """Check if users table exists."""
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'users'
    );
    """
    try:
        result = execute_query(query, fetch=True)
        if result and result[0][0]:
            print("✓ Users table exists")
            return True
        else:
            print("✗ Users table does not exist")
            return False
    except Exception as e:
        print(f"✗ Failed to check users table: {str(e)}")
        return False
