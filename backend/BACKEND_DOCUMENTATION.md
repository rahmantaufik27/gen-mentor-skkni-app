# Backend Module Documentation

## Overview

This backend module implements a RESTful API for quiz management using Flask. It provides endpoints for:
- Creating and managing quiz sessions
- Serving randomized questions
- Validating and recording answers
- Calculating scores
- Storing results persistently

## Architecture

### Layered Architecture

```
┌─────────────────────────────────────────────┐
│         API Routes (routes/)                │
│  - Handle HTTP requests/responses           │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│      Controllers (controllers/)             │
│  - Orchestrate business logic               │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│        Services (services/)                 │
│  - Core functionality:                      │
│    * Question loading & management          │
│    * Session creation & management          │
│    * Result calculation & storage           │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│    Data Models & Storage (types/, data/)    │
│  - Models: Question, Choice, QuizSession    │
│  - Storage: JSON files                      │
└─────────────────────────────────────────────┘
```

## Modules

### 1. **Data Models** (`types/models.py`)

Defines all data structures using Python dataclasses:

#### `Choice`
```python
@dataclass
class Choice:
    id: str              # "a", "b", "c", "d"
    text: str            # Answer text
    is_correct: bool     # Whether this is the correct answer
```

#### `Question`
```python
@dataclass
class Question:
    id: str                      # Unique question ID
    question_text: str           # The question
    category: str                # e.g., "Geography", "Science"
    difficulty: str              # "easy", "medium", "hard"
    choices: List[Choice]        # Answer choices
    explanation: str             # Why the answer is correct
    answer_type: str             # Type of question
```

#### `UserAnswer`
```python
@dataclass
class UserAnswer:
    question_id: str             # Which question answered
    selected_choice_id: str      # Which choice selected
    is_correct: bool             # Was it correct?
    answered_at: str             # ISO timestamp
```

#### `QuizSession`
```python
@dataclass
class QuizSession:
    session_id: str              # Unique session ID
    questions: List[Question]    # Questions in this session
    user_answers: List[UserAnswer]  # Answers provided
    started_at: str              # Start timestamp
    completed_at: Optional[str]  # End timestamp
    is_completed: bool           # Session finished?
```

#### `QuizResult`
```python
@dataclass
class QuizResult:
    session_id: str              # Which session
    total_questions: int         # 30
    correct_answers: int         # Number correct
    wrong_answers: int           # Number wrong
    score_percentage: float      # Calculated percentage
    is_passed: bool              # Pass/fail status
    completed_at: str            # When completed
    answers: List[dict]          # Detailed answer review
```

### 2. **Services Layer** (`services/`)

#### `QuestionLoader` (`question_loader.py`)

Loads and manages questions from JSON:

```python
loader = QuestionLoader(data_dir)

# Load all questions
questions = loader.load_questions()

# Get specific question
question = loader.get_question_by_id("q001")

# Get questions by category
geography = loader.get_questions_by_category("Geography")

# Validate answer
is_correct = loader.validate_question_answer("q001", "b")
```

**Features:**
- Caches questions in memory
- Validates answers against stored correct answers
- Provides category filtering
- Raises errors for missing files

#### `QuizSessionManager` (`session_manager.py`)

Manages quiz sessions and scoring:

```python
manager = QuizSessionManager(question_loader)

# Create new session
session = manager.create_session()

# Submit answer
manager.submit_answer(session_id, question_id, choice_id)

# Complete session
result = manager.complete_session(session_id)

# Get results
result = manager.get_results(session_id)
```

**Key Methods:**
- `create_session()` - Creates session with 30 randomized questions
- `submit_answer()` - Records and validates user answer
- `complete_session()` - Finalizes session and calculates results
- `get_results()` - Retrieves calculated results
- `get_session_progress()` - Returns progress info
- `_calculate_results()` - Internal scoring logic

**Scoring Logic:**
```python
# Percentage calculation
score_percentage = (correct_answers / total_questions) * 100

# Pass/fail determination
is_passed = score_percentage >= 75  # 75% = 23/30
```

#### `SessionStorage` (`session_storage.py`)

Persists results to JSON files:

```python
storage = SessionStorage(storage_dir)

# Save result
storage.save_result(result)

# Load result
result_data = storage.get_result(session_id)

# Get all results
all_results = storage.get_all_results()

# Get summary
summary = storage.get_results_summary()
```

**Storage Structure:**
```
backend/storage/
├── quiz_results.json          # All results summary
└── sessions/
    ├── {uuid1}.json           # Session 1 results
    ├── {uuid2}.json           # Session 2 results
    └── ...
```

### 3. **Controllers** (`controllers/`)

#### `QuizController` (`quiz_controller.py`)

Orchestrates business logic:

```python
controller = QuizController(loader, manager, storage)

# Start quiz
result = controller.start_quiz()

# Get question
result = controller.get_question(session_id, index)

# Submit answer
result = controller.submit_answer(session_id, question_id, choice_id)

# Complete quiz
result = controller.complete_quiz(session_id)
```

**Methods:**
- `start_quiz()` - Creates session and returns first question
- `get_question()` - Retrieves specific question
- `submit_answer()` - Processes answer submission
- `get_progress()` - Returns session progress
- `complete_quiz()` - Finalizes and saves results
- `get_results()` - Retrieves saved results
- `get_all_results()` - Gets all quiz history

**Return Format:**
```python
{
    "success": True/False,
    "error": "Error message if failed",
    "result": {...},  # Result data if successful
    "progress": {...} # Progress data if applicable
}
```

### 4. **Routes** (`routes/`)

#### `QuizRoutes` (`quiz_routes.py`)

Defines API endpoints:

```python
init_quiz_routes(app, controller)
```

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/quiz/start` | Start new quiz |
| GET | `/api/quiz/question/{id}/{idx}` | Get question |
| POST | `/api/quiz/submit-answer` | Submit answer |
| GET | `/api/quiz/progress/{id}` | Get progress |
| POST | `/api/quiz/complete/{id}` | Complete quiz |
| GET | `/api/quiz/results/{id}` | Get results |
| GET | `/api/quiz/all-results` | Get all results |
| GET | `/api/quiz/results-summary` | Get summary |
| GET | `/api/quiz/health` | Health check |

### 5. **Main Application** (`app.py`)

Flask application factory:

```python
def create_app(config=None):
    app = Flask(__name__)
    
    # Setup services
    question_loader = QuestionLoader(data_dir)
    session_manager = QuizSessionManager(question_loader)
    storage = SessionStorage(storage_dir)
    
    # Setup controller and routes
    controller = QuizController(...)
    init_quiz_routes(app, controller)
    
    return app

# Run
if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)
```

**Configuration:**
- Host: `127.0.0.1` (localhost only)
- Port: `5000`
- Debug: `True` (for development)
- CORS: Enabled for all origins

## Data Flow

### Quiz Start Flow
```
1. Frontend: POST /api/quiz/start
2. Route: Calls controller.start_quiz()
3. Controller: Calls session_manager.create_session()
4. SessionManager: 
   - Calls question_loader.load_questions()
   - Creates 30-question session
   - Randomizes questions
   - Returns QuizSession object
5. Controller: Returns JSON with session_id and first question
6. Frontend: Receives data and displays first question
```

### Answer Submission Flow
```
1. Frontend: POST /api/quiz/submit-answer {session_id, question_id, choice_id}
2. Route: Calls controller.submit_answer(...)
3. Controller: Calls session_manager.submit_answer(...)
4. SessionManager:
   - Validates answer via question_loader
   - Creates UserAnswer object
   - Adds to session
   - Auto-completes if all answered
5. Returns progress JSON
6. Frontend: Shows next question or results
```

### Results Calculation Flow
```
1. Complete quiz (all 30 questions answered)
2. SessionManager._calculate_results():
   - Count correct answers
   - Calculate percentage
   - Determine pass/fail (>= 75%)
   - Build detailed answer review
   - Return QuizResult
3. Storage.save_result():
   - Saves to quiz_results.json
   - Saves individual session JSON
4. Return results to frontend
```

## JSON Data Format

### Questions File (`data/questions.json`)
```json
{
  "questions": [
    {
      "id": "q001",
      "question_text": "What is 2 + 2?",
      "category": "Mathematics",
      "difficulty": "easy",
      "answer_type": "multiple_choice",
      "choices": [
        {"id": "a", "text": "3", "is_correct": false},
        {"id": "b", "text": "4", "is_correct": true},
        {"id": "c", "text": "5", "is_correct": false},
        {"id": "d", "text": "6", "is_correct": false}
      ],
      "explanation": "2 + 2 equals 4"
    }
  ]
}
```

### Results File (`storage/quiz_results.json`)
```json
[
  {
    "session_id": "uuid-1234",
    "total_questions": 30,
    "correct_answers": 25,
    "wrong_answers": 5,
    "score_percentage": 83.33,
    "is_passed": true,
    "completed_at": "2026-05-30T10:30:00",
    "answers": [...]
  }
]
```

### Session Result (`storage/sessions/{uuid}.json`)
```json
{
  "session_id": "uuid-1234",
  "total_questions": 30,
  "correct_answers": 25,
  "wrong_answers": 5,
  "score_percentage": 83.33,
  "is_passed": true,
  "completed_at": "2026-05-30T10:30:00",
  "answers": [
    {
      "question_id": "q001",
      "question_text": "Question?",
      "category": "Geography",
      "difficulty": "easy",
      "your_answer": "Selected answer",
      "correct_answer": "Correct answer",
      "is_correct": true,
      "explanation": "Why correct"
    }
  ]
}
```

## Error Handling

### Error Responses
```json
{
  "success": false,
  "error": "Descriptive error message"
}
```

### HTTP Status Codes
- `200` - Success
- `400` - Bad request (validation failed)
- `404` - Not found (endpoint or resource)
- `500` - Server error

### Common Errors
| Error | Cause | Solution |
|-------|-------|----------|
| "Questions file not found" | Missing data/questions.json | Create file with 30 questions |
| "Session not found" | Invalid session ID | Check session ID is correct |
| "Question not found" | Invalid question index | Check 0-29 range |
| "Failed to submit answer" | Session already completed | Start new quiz |

## Testing

### Unit Testing Structure

Would add tests for:
```python
tests/
├── test_models.py           # Model dataclass tests
├── test_question_loader.py  # Question loading
├── test_session_manager.py  # Session and scoring logic
├── test_session_storage.py  # JSON persistence
├── test_controller.py       # Business logic
└── test_routes.py           # API endpoints
```

### Example Test
```python
def test_score_calculation():
    result = QuizResult(
        session_id="test",
        total_questions=30,
        correct_answers=23,
        wrong_answers=7,
        score_percentage=76.67,
        is_passed=True,
        completed_at="now",
        answers=[]
    )
    assert result.is_passed == True
    assert result.score_percentage >= 75
```

## Performance Considerations

### Current Performance
- **Session creation:** < 100ms (loads 30 questions)
- **Answer validation:** < 10ms (O(1) lookup)
- **Results calculation:** < 50ms (O(n) through 30 answers)
- **JSON write:** < 100ms (one file write)

### Scalability
- **In-memory sessions:** Limited by available RAM
- **Concurrent users:** Flask development server ~10-50
- **Production deployment:** Use Gunicorn/uWSGI

### Optimization Opportunities
- Cache results for repeated queries
- Batch JSON writes
- Use database for persistent storage
- Implement result pagination
- Add compression for large responses

## Security Considerations

### Current Limitations
1. No authentication - anyone can access
2. No authorization - no user isolation
3. No input validation - assumes valid data
4. No rate limiting - no DOS protection
5. CORS enabled for all origins

### Production Recommendations
1. Add JWT authentication
2. Implement role-based access control
3. Add input validation on all endpoints
4. Implement rate limiting
5. Use HTTPS/TLS encryption
6. Add request logging
7. Implement CSRF protection
8. Validate file uploads

## Future Enhancements

### Phase 2 - Database Migration
```python
# Replace JSON with PostgreSQL
from sqlalchemy import create_engine, Column, String
from sqlalchemy.orm import sessionmaker

engine = create_engine('postgresql://...')
Session = sessionmaker(bind=engine)
```

### Phase 3 - Advanced Features
- User authentication and profiles
- Question categorization and difficulty levels
- Timed quizzes
- Multiple quiz types (true/false, short answer)
- Question bank management interface
- Analytics dashboard
- Question recommendations

### Phase 4 - Analytics
- User performance tracking
- Question difficulty analysis
- Common misconceptions
- Learning path recommendations
- Adaptive difficulty

### Phase 5 - Distribution
- Dockerize application
- Deploy to cloud (AWS, Azure, GCP)
- Implement caching (Redis)
- Scale horizontally with load balancer
- CDN for static assets

## Maintenance

### Regular Tasks
- Monitor API response times
- Check error logs weekly
- Backup quiz_results.json daily
- Review session storage size
- Update dependencies monthly

### Troubleshooting
- Check backend logs for errors
- Verify data/questions.json is valid JSON
- Check storage/ directory permissions
- Monitor disk space for results storage
- Clear old sessions periodically

## API Usage Examples

### Python Client
```python
import httpx

BASE_URL = "http://127.0.0.1:5000/api/quiz"

# Start quiz
resp = httpx.post(f"{BASE_URL}/start")
session_id = resp.json()["session_id"]

# Get question
resp = httpx.get(f"{BASE_URL}/question/{session_id}/0")
question = resp.json()["question"]

# Submit answer
resp = httpx.post(f"{BASE_URL}/submit-answer", json={
    "session_id": session_id,
    "question_id": "q001",
    "choice_id": "b"
})

# Get results
resp = httpx.get(f"{BASE_URL}/results/{session_id}")
results = resp.json()["result"]
```

### JavaScript/Fetch
```javascript
const BASE_URL = "http://127.0.0.1:5000/api/quiz";

// Start quiz
const startResp = await fetch(`${BASE_URL}/start`, { method: "POST" });
const { session_id } = await startResp.json();

// Submit answer
const answerResp = await fetch(`${BASE_URL}/submit-answer`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    session_id,
    question_id: "q001",
    choice_id: "b"
  })
});
```

## Documentation Structure

- **This file** - Backend architecture and design
- **SETUP_AND_RUN.md** - Installation and running instructions
- **API_DOCUMENTATION.md** - Detailed API reference (separate file)
- **DEPLOYMENT.md** - Production deployment guide (future)

## Contact & Support

For issues or questions:
1. Check SETUP_AND_RUN.md troubleshooting section
2. Review API responses for error messages
3. Check backend logs (terminal output)
4. Verify data/questions.json integrity

## Version History

**v1.0.0 (2026-05-30)**
- Initial implementation
- 30 question dataset
- Modular architecture
- JSON-based persistence
- Full frontend integration
