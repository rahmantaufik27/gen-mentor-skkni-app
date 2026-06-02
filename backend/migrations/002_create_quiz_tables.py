"""Quiz tables migration."""

from config.database import execute_query


def create_quiz_tables():
    """Create quiz-related tables if they don't exist."""
    
    # Create quiz_attempts table
    quiz_attempts_query = """
    CREATE TABLE IF NOT EXISTS quiz_attempts (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        started_at TIMESTAMP DEFAULT NOW(),
        completed_at TIMESTAMP,
        total_questions INT NOT NULL,
        correct_answers INT DEFAULT 0,
        total_score INT DEFAULT 0,
        pass_fail VARCHAR(10),
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS idx_quiz_attempts_user_id ON quiz_attempts(user_id);
    CREATE INDEX IF NOT EXISTS idx_quiz_attempts_completed_at ON quiz_attempts(completed_at);
    """
    
    # Create quiz_attempt_details table (per-question results)
    quiz_attempt_details_query = """
    CREATE TABLE IF NOT EXISTS quiz_attempt_details (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        quiz_attempt_id UUID NOT NULL REFERENCES quiz_attempts(id) ON DELETE CASCADE,
        question_number INT NOT NULL,
        question_text TEXT NOT NULL,
        unit_code VARCHAR(50) NOT NULL,
        bloom_level VARCHAR(3) NOT NULL,
        selected_answer VARCHAR(1),
        correct_answer VARCHAR(1) NOT NULL,
        is_correct BOOLEAN DEFAULT FALSE,
        score_earned INT DEFAULT 0,
        created_at TIMESTAMP DEFAULT NOW()
    );
    
    CREATE INDEX IF NOT EXISTS idx_quiz_attempt_details_quiz_attempt_id ON quiz_attempt_details(quiz_attempt_id);
    CREATE INDEX IF NOT EXISTS idx_quiz_attempt_details_bloom_level ON quiz_attempt_details(bloom_level);
    """
    
    # Create user_mastery table (unit-level mastery tracking)
    user_mastery_query = """
    CREATE TABLE IF NOT EXISTS user_mastery (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        unit_code VARCHAR(50) NOT NULL,
        total_score INT DEFAULT 0,
        max_possible_score INT DEFAULT 36,
        mastery_status VARCHAR(20),
        last_updated TIMESTAMP DEFAULT NOW(),
        created_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(user_id, unit_code)
    );
    
    CREATE INDEX IF NOT EXISTS idx_user_mastery_user_id ON user_mastery(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_mastery_status ON user_mastery(mastery_status);
    """
    
    try:
        execute_query(quiz_attempts_query)
        print("✓ quiz_attempts table created successfully or already exists")
        
        execute_query(quiz_attempt_details_query)
        print("✓ quiz_attempt_details table created successfully or already exists")
        
        execute_query(user_mastery_query)
        print("✓ user_mastery table created successfully or already exists")
        
        return True
    except Exception as e:
        print(f"✗ Failed to create quiz tables: {str(e)}")
        return False


def check_quiz_tables_exist():
    """Check if all quiz tables exist."""
    tables_to_check = ["quiz_attempts", "quiz_attempt_details", "user_mastery"]
    
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
