# Quiz Application - Setup & Run Instructions

## Project Overview

This is a complete quiz assessment system with:
- **Frontend:** Streamlit-based Python application
- **Backend:** Flask-based REST API
- **Data:** JSON-based dataset storage
- **Architecture:** Modular, scalable, database-ready

## Project Structure

```
gen-app/
├── frontend/
│   ├── pages/
│   │   ├── quiz.py              # Quiz page component
│   │   └── ... (other pages)
│   ├── utils/
│   │   ├── quiz_api.py          # Quiz API client
│   │   ├── request_api.py       # General API client
│   │   └── ... (other utilities)
│   ├── main.py                   # Main Streamlit app
│   ├── config.py                 # Frontend config
│   └── requirements.txt          # Frontend dependencies
│
└── backend/
    ├── app.py                    # Flask application entry point
    ├── requirements.txt          # Backend dependencies
    ├── data/
    │   └── questions.json        # Quiz questions dataset
    ├── storage/                  # Quiz results storage
    │   ├── quiz_results.json     # All results summary
    │   └── sessions/             # Individual session results
    ├── routes/
    │   ├── __init__.py
    │   └── quiz_routes.py        # Quiz API routes
    ├── controllers/
    │   ├── __init__.py
    │   └── quiz_controller.py    # Quiz business logic
    ├── services/
    │   ├── __init__.py
    │   ├── question_loader.py    # Load questions from JSON
    │   ├── session_manager.py    # Manage quiz sessions
    │   └── session_storage.py    # Persist results to JSON
    ├── types/
    │   ├── __init__.py
    │   └── models.py             # Data models
    ├── utils/
    ├── middleware/
    └── storage/
```

## Installation

### Backend Setup

1. **Navigate to backend directory:**
```bash
cd gen-app/backend
```

2. **Create a virtual environment (optional but recommended):**
```bash
python -m venv venv
source venv/Scripts/activate  # On Windows
# or
source venv/bin/activate      # On macOS/Linux
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

### Frontend Setup

1. **Navigate to frontend directory:**
```bash
cd gen-app/frontend
```

2. **Ensure dependencies are installed:**
```bash
pip install -r requirements.txt
```

3. **Verify backend endpoint configuration in `config.py`:**
```python
backend_endpoint = "http://127.0.0.1:5000/"
```

## Running the Application

### Method 1: Run Backend and Frontend Separately (Recommended)

**Terminal 1 - Start Backend:**
```bash
cd gen-app/backend
python app.py
```

You should see:
```
Starting Quiz Backend Server...
Server running on http://127.0.0.1:5000
 * Running on http://127.0.0.1:5000
```

**Terminal 2 - Start Frontend:**
```bash
cd gen-app/frontend
streamlit run main.py
```

The frontend will open at `http://localhost:8501`

### Method 2: Automated Startup (Windows PowerShell)

Create `start_all.ps1`:
```powershell
# Start backend
Start-Process powershell -ArgumentList "cd '.\gen-app\backend' -and python app.py"

# Start frontend
Start-Process powershell -ArgumentList "cd '.\gen-app\frontend' -and streamlit run main.py"

Write-Host "Backend and Frontend started!"
```

Run it:
```bash
.\start_all.ps1
```

## API Endpoints

### Base URL
```
http://127.0.0.1:5000/api/quiz
```

### Endpoints

#### 1. **Start Quiz**
```
POST /api/quiz/start
```
Returns: New session ID and first question

Response:
```json
{
  "success": true,
  "session_id": "uuid-string",
  "total_questions": 30,
  "first_question": {
    "id": "q001",
    "question_text": "What is the capital of France?",
    "category": "Geography",
    "difficulty": "easy",
    "choices": [
      {"id": "a", "text": "London"},
      {"id": "b", "text": "Paris"},
      ...
    ]
  }
}
```

#### 2. **Get Question**
```
GET /api/quiz/question/{session_id}/{question_index}
```
Parameters:
- `session_id`: Quiz session ID
- `question_index`: 0-based question index (0-29)

Response:
```json
{
  "success": true,
  "question_index": 0,
  "question": { ... },
  "progress": {
    "session_id": "uuid-string",
    "total_questions": 30,
    "answered_questions": 0,
    "remaining_questions": 30,
    "progress_percentage": 0
  }
}
```

#### 3. **Submit Answer**
```
POST /api/quiz/submit-answer
Content-Type: application/json

{
  "session_id": "uuid-string",
  "question_id": "q001",
  "choice_id": "b"
}
```

Response:
```json
{
  "success": true,
  "progress": { ... },
  "is_completed": false
}
```

#### 4. **Get Progress**
```
GET /api/quiz/progress/{session_id}
```

Response:
```json
{
  "success": true,
  "progress": {
    "total_questions": 30,
    "answered_questions": 5,
    "remaining_questions": 25,
    "progress_percentage": 16.67,
    "is_completed": false
  }
}
```

#### 5. **Complete Quiz**
```
POST /api/quiz/complete/{session_id}
```

Returns complete results and saves to JSON storage.

#### 6. **Get Results**
```
GET /api/quiz/results/{session_id}
```

Returns detailed quiz results with answer review.

#### 7. **Get All Results**
```
GET /api/quiz/all-results
```

Returns all stored quiz results.

#### 8. **Get Results Summary**
```
GET /api/quiz/results-summary
```

Returns summary statistics of all quizzes.

#### 9. **Health Check**
```
GET /api/quiz/health
```

## Quiz Rules & Scoring

### Quiz Configuration
- **Total Questions:** 30
- **Question Types:** Multiple Choice
- **Randomization:** Questions are shuffled for each attempt
- **No Time Limit:** Unlimited time per question
- **Sequential:** Cannot go back to previous questions

### Scoring Formula
```
Score % = (Correct Answers / Total Questions) × 100
Score % = (Correct Answers / 30) × 100
```

### Pass/Fail Criteria
- **Passing Score:** 75%
- **Minimum Correct:** 23 out of 30
- **Failing Score:** Below 75%

### Examples
- 23/30 = 76.67% → ✅ PASS
- 22/30 = 73.33% → ❌ FAIL
- 25/30 = 83.33% → ✅ PASS
- 20/30 = 66.67% → ❌ FAIL

## Data Storage

### Questions Dataset
File: `backend/data/questions.json`

Format:
```json
{
  "questions": [
    {
      "id": "q001",
      "question_text": "Question text here?",
      "category": "Geography",
      "difficulty": "easy",
      "answer_type": "multiple_choice",
      "choices": [
        {"id": "a", "text": "Option A", "is_correct": false},
        {"id": "b", "text": "Option B", "is_correct": true},
        {"id": "c", "text": "Option C", "is_correct": false},
        {"id": "d", "text": "Option D", "is_correct": false}
      ],
      "explanation": "Explanation of the correct answer"
    }
  ]
}
```

### Results Storage
- File: `backend/storage/quiz_results.json` - Summary of all results
- Directory: `backend/storage/sessions/` - Individual session files

Each session is saved as `{session_id}.json` with complete results.

## Frontend Integration

### Using the Quiz Page

1. **Navigate to Quiz:** Click "Quiz" in the sidebar
2. **Start Quiz:** Click "Start Quiz" button
3. **Answer Questions:** Select an answer and click "Submit Answer"
4. **View Results:** After completing all questions, results are displayed
5. **Review Answers:** Expand each question to see correct answer and explanation
6. **Retake Quiz:** Click "Take Another Quiz" to start fresh

### API Client

The frontend uses `utils/quiz_api.py` for all quiz API calls:

```python
from utils.quiz_api import start_quiz, get_question, submit_answer, get_results

# Start a quiz
result = start_quiz()
session_id = result['session_id']

# Get a question
q = get_question(session_id, 0)

# Submit answer
submit_answer(session_id, 'q001', 'b')

# Get results
results = get_results(session_id)
```

## Environment Configuration

### Backend Configuration

File: `backend/app.py`

```python
# Configuration
app.config.update(
    JSON_SORT_KEYS=False,
    JSONIFY_PRETTYPRINT_REGULAR=True
)

# CORS is enabled for all origins
CORS(app)
```

### Frontend Configuration

File: `frontend/config.py`

```python
backend_endpoint = "http://127.0.0.1:5000/"
use_mock_data = False
use_search = True
```

## Troubleshooting

### Backend won't start

1. **Check Python version:** Requires Python 3.8+
```bash
python --version
```

2. **Check dependencies:**
```bash
pip install -r requirements.txt --upgrade
```

3. **Check port availability:**
```bash
# Windows
netstat -ano | findstr :5000

# macOS/Linux
lsof -i :5000
```

### Frontend can't connect to backend

1. **Verify backend is running:** Visit `http://127.0.0.1:5000` in browser
2. **Check endpoint in config.py:** Should be `http://127.0.0.1:5000/`
3. **Check CORS:** Backend has CORS enabled for all origins
4. **Check network:** Ensure no firewall blocking localhost traffic

### Quiz session errors

1. **Session not found:** Session may have expired (in-memory storage)
2. **Question not loading:** Check `data/questions.json` exists
3. **Results not saving:** Check `storage/` directory permissions

## Testing

### Manual Testing

1. **Start Backend**
2. **Test Health Endpoint:**
```bash
curl http://127.0.0.1:5000/api/quiz/health
```

3. **Test Quiz Flow:**
   - Start quiz
   - Get first question
   - Submit answer
   - Check progress
   - Complete and get results

### Example cURL Tests

```bash
# Start quiz
curl -X POST http://127.0.0.1:5000/api/quiz/start

# Get question
curl http://127.0.0.1:5000/api/quiz/question/{session_id}/0

# Submit answer
curl -X POST http://127.0.0.1:5000/api/quiz/submit-answer \
  -H "Content-Type: application/json" \
  -d '{"session_id":"...","question_id":"q001","choice_id":"b"}'

# Get results
curl http://127.0.0.1:5000/api/quiz/results/{session_id}
```

## Architecture & Design

### Modular Structure

```
routes/           → API endpoints
  ↓
controllers/      → Business logic
  ↓
services/         → Core functionality
  ↓
types/            → Data models
  ↓
storage/          → Persistence
```

### Data Flow

1. **Frontend** makes API call to **Backend**
2. **Route** receives request, calls **Controller**
3. **Controller** calls **Service** methods
4. **Service** uses **Models** and accesses **Storage**
5. **Response** is returned as JSON

### Future Database Migration

Current structure is designed for easy migration to PostgreSQL/Neo4j:

1. **Services Layer** abstracts data access
2. **Models** are dataclass-based
3. **Storage** can be replaced with database ORM (SQLAlchemy)
4. **Controllers** don't depend on storage implementation

To migrate:
- Replace `SessionStorage.py` with database adapter
- Update models to use SQLAlchemy ORM
- Add database migrations
- No route/controller changes needed

## Performance Notes

- **In-Memory Sessions:** Sessions are stored in memory, cleared on restart
- **JSON Storage:** Results are persisted to JSON files
- **Question Caching:** Questions are cached in memory after first load
- **No Time Limit:** Quiz can be taken at user's pace

## Security Notes

- CORS enabled for all origins (configure for production)
- No authentication/authorization implemented
- Suitable for development/testing only
- For production: Add authentication, validate inputs, use HTTPS

## Dependencies

### Backend
- Flask 3.0.0
- flask-cors 4.0.0
- Werkzeug 3.0.0

### Frontend
- Streamlit 1.40.0
- httpx (for API calls)
- Various streamlit extensions

## Support & Debugging

### Enable Debug Mode

Backend debug mode is already enabled in `app.py`:
```python
app.run(host="127.0.0.1", port=5000, debug=True)
```

### Check Logs

1. **Backend logs:** Displayed in terminal where backend is running
2. **Frontend logs:** Displayed in terminal where streamlit is running
3. **API responses:** Available in browser console (F12)

### Common Issues

| Issue | Solution |
|-------|----------|
| Module not found | Run `pip install -r requirements.txt` |
| Port already in use | Kill process on port 5000 or change port |
| CORS error | Verify backend is running with CORS enabled |
| Session not found | Start new quiz, session expires on backend restart |
| Questions not loading | Check `data/questions.json` exists and is valid JSON |

## License

This project is part of Gen-Mentor learning platform.

## Version

Current Version: 1.0.0
Last Updated: 2026-05-30
