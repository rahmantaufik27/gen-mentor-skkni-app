"""
Authentication Setup and Testing Guide
========================================

This document explains how to set up and test the new authentication module.

## Backend Setup

### 1. Install Dependencies
Navigate to the backend directory and install the required packages:

```bash
cd backend/
pip install -r requirements.txt
```

This will install:
- psycopg2-binary: PostgreSQL adapter for Python
- bcrypt: Password hashing library
- uuid6: For UUID generation

### 2. Verify Database Configuration
Check that `backend/db.ini` contains the correct PostgreSQL credentials:

```ini
[postgresql]
host=localhost
database=genmentorskknidb
user=postgres
password=1985
port=5432
```

### 3. Start the Backend Server
From the backend directory:

```bash
python app.py
```

You should see output like:
```
==================================================
Starting Gen-Mentor Backend Server...
==================================================
Endpoints available at:
  - API Root: http://127.0.0.1:5000
  - Register: POST http://127.0.0.1:5000/api/auth/register
  - Login: POST http://127.0.0.1:5000/api/auth/login
  - Logout: POST http://127.0.0.1:5000/api/auth/logout
==================================================
```

The server will automatically create the `users` table if it doesn't exist.

## Frontend Setup

### 1. Install Frontend Dependencies
Navigate to the frontend directory and install dependencies:

```bash
cd frontend/
pip install -r requirements.txt
```

Ensure `httpx` is installed for making HTTP requests to the backend.

### 2. Start Streamlit
From the frontend directory:

```bash
streamlit run main.py
```

This will open the application in your browser.

## Testing the Authentication Flow

### Test 1: Registration

1. Open the Streamlit app in your browser (usually http://localhost:8501)
2. Navigate to the Register page (look for the pages dropdown or use direct URL)
3. Fill in the form:
   - First Name: John
   - Last Name: Doe
   - Email: john@example.com
   - Password: TestPassword123
   - Confirm Password: TestPassword123
4. Click "Create Account"
5. You should see a success message and be redirected to the Login page

**What happens behind the scenes:**
- Frontend sends POST request to http://127.0.0.1:5000/api/auth/register
- Backend validates all inputs
- Backend checks if email already exists
- Backend hashes password with bcrypt
- Backend inserts user record into PostgreSQL users table
- Frontend stores success and redirects to login page

### Test 2: Login

1. From the Login page (or navigate to it)
2. Fill in the form:
   - Email: john@example.com
   - Password: TestPassword123
3. Click "Sign In"
4. You should see a success message and be redirected to the Learner Profile page
5. Check that the userId is stored in session_state

**What happens behind the scenes:**
- Frontend sends POST request to http://127.0.0.1:5000/api/auth/login
- Backend finds user by email
- Backend verifies password hash using bcrypt
- Backend creates Flask session
- Frontend stores user info (id, name, email) in st.session_state
- Frontend persists user data to data_store.json
- User is redirected to main app

### Test 3: Invalid Login

1. Try logging in with:
   - Email: john@example.com
   - Password: WrongPassword
2. You should see error: "Invalid email or password"

### Test 4: Duplicate Registration

1. Try to register again with:
   - Email: john@example.com (same email as before)
2. You should see error: "Email already registered"

### Test 5: Password Validation

1. Try to register with:
   - Password: short (less than 8 characters)
2. You should see error: "Password must be at least 8 characters"

### Test 6: Password Mismatch

1. Try to register with:
   - Password: TestPassword123
   - Confirm Password: DifferentPassword
2. You should see error: "Passwords do not match"

## API Endpoints Reference

### POST /api/auth/register
Registers a new user.

**Request:**
```json
{
    "full_name": "John Doe",
    "email": "john@example.com",
    "password": "TestPassword123",
    "confirm_password": "TestPassword123"
}
```

**Success Response (201):**
```json
{
    "message": "User registered successfully",
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "success": true
}
```

**Error Response (400/409):**
```json
{
    "error": "Email already registered",
    "success": false
}
```

### POST /api/auth/login
Authenticates a user and creates a session.

**Request:**
```json
{
    "email": "john@example.com",
    "password": "TestPassword123"
}
```

**Success Response (200):**
```json
{
    "message": "Login successful",
    "user": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "full_name": "John Doe",
        "email": "john@example.com"
    },
    "success": true
}
```

**Error Response (401):**
```json
{
    "error": "Invalid email or password",
    "success": false
}
```

### POST /api/auth/logout
Clears the user session.

**Success Response (200):**
```json
{
    "message": "Logged out successfully",
    "success": true
}
```

### GET /api/auth/me
Gets the current authenticated user (requires active session).

**Success Response (200):**
```json
{
    "user": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "full_name": "John Doe",
        "email": "john@example.com",
        "created_at": "2024-01-15T10:30:00"
    },
    "success": true
}
```

**Error Response (401):**
```json
{
    "error": "Not authenticated",
    "success": false
}
```

## Database Schema

The users table is created automatically on first run:

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
```

## Security Features Implemented

1. **Password Hashing**: Uses bcrypt with 12 rounds (industry standard)
2. **SQL Injection Prevention**: Uses parameterized queries
3. **Duplicate Email Prevention**: Unique constraint on email column
4. **Email Validation**: Basic format validation
5. **Password Requirements**: Minimum 8 characters
6. **Session Management**: Flask sessions stored server-side
7. **Secure Session Cookies**: HTTPOnly and SameSite flags set

## Troubleshooting

### Issue: "Cannot connect to backend server"
- Ensure backend is running on localhost:5000
- Check that Flask app started successfully
- Verify no firewall is blocking port 5000

### Issue: "Database connection failed"
- Verify PostgreSQL is running on localhost:5432
- Check db.ini file has correct credentials
- Verify database name: genmentorskknidb exists
- Check user 'postgres' has appropriate permissions

### Issue: "Email already registered"
- The email is already in the database
- Use a different email for testing
- Or manually delete the user from the database

### Issue: "Password must be at least 8 characters"
- Use a password with at least 8 characters
- Password requirements are enforced both frontend and backend

## Next Steps

After authentication is working:

1. Implement password reset functionality
2. Add email verification for new accounts
3. Add rate limiting to prevent brute force attacks
4. Implement protected routes that check authentication
5. Add refresh token mechanism for better security
6. Implement OAuth/SSO integration (if needed)
7. Add audit logging for authentication events

## File Structure

```
backend/
├── app.py                          # Main Flask app (updated with auth)
├── requirements.txt                 # Dependencies (updated)
├── db.ini                           # Database config
├── config/
│   ├── __init__.py
│   └── database.py                 # Database connection module
├── migrations/
│   ├── __init__.py
│   └── 001_create_users_table.py   # User table creation
├── services/
│   ├── auth_service.py             # Authentication logic
│   └── ...
├── controllers/
│   ├── auth_controller.py          # Authentication controller
│   └── ...
└── routes/
    ├── auth_routes.py              # Auth endpoints
    └── ...

frontend/
├── pages/
│   ├── register.py                 # Registration page (new)
│   ├── login.py                    # Login page (new)
│   └── ...
└── utils/
    └── state.py                    # State management (updated)
```
"""
