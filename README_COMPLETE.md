# Gen-Mentor Quiz System - Complete Setup Guide

## 📋 Overview

This is a complete quiz assessment system built with:
- **Backend**: Flask (Python) with REST API
- **Frontend**: Streamlit (Python) web interface
- **Database**: JSON-based storage (questions, results)

The system loads questions from a JSON file and presents them as a 30-question quiz with automatic scoring and pass/fail determination (75% threshold = 23/30 correct).

## 🏗️ Project Structure

```
gen-app/
├── backend/                      # Flask REST API
│   ├── app.py                   # Flask app factory
│   ├── models/                  # Data models
│   │   └── model.py             # Question, Choice, Session, Result dataclasses
│   ├── services/                # Business logic
│   │   ├── question_loader.py   # Load & parse questions.json
│   │   ├── session_manager.py   # Create sessions, manage answers
│   │   └── session_storage.py   # Persist results to JSON
│   ├── controllers/             # Orchestration layer
│   │   └── quiz_controller.py   # Coordinate services for API
│   ├── routes/                  # API endpoints
│   │   └── quiz_routes.py       # 9 quiz API endpoints
│   ├── data/                    # Question data
│   │   └── extracted_refined_generated_questions_fewshot_perunit_*.json
│   ├── storage/                 # Results storage (auto-created)
│   └── requirements.txt         # Python dependencies
│
├── frontend/                    # Streamlit web interface
│   ├── main.py                  # App entry point with navigation
│   ├── config.py                # Configuration
│   ├── pages/                   # Page components
│   │   ├── quiz.py              # Quiz page
│   │   ├── dashboard.py         # Dashboard page
│   │   ├── learning_path.py     # Learning path page
│   │   └── learner_profile.py   # Profile page
│   ├── utils/                   # Utilities
│   │   └── quiz_api.py          # API client for backend
│   ├── requirements.txt         # Python dependencies
│   └── .streamlit/
│       └── config.toml          # Streamlit config
│
├── BACKEND_FIX_SUMMARY.md       # What was fixed
├── TESTING_BACKEND_FIX.md       # Testing guide
└── FORMAT_TRANSFORMATION_REFERENCE.md  # Data format details
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- pip (Python package manager)

### Installation & Setup

#### 1. Install Backend Dependencies
```bash
cd backend
pip install -r requirements.txt
```

Backend requirements:
- Flask 3.0.0
- flask-cors 4.0.0
- python-dateutil

#### 2. Install Frontend Dependencies
```bash
cd frontend
pip install -r requirements.txt
```

Frontend requirements:
- streamlit 1.40.0
- httpx (for API calls)

### Running the System

#### Terminal 1: Start Backend
```bash
cd backend
python app.py
```

Expected output:
```
 * Running on http://127.0.0.1:5000/
```

#### Terminal 2: Start Frontend
```bash
cd frontend
streamlit run main.py
```

Expected output:
```
  You can now view your Streamlit app in your browser.

  URL: http://localhost:8501
```

#### Browser
Open http://localhost:8501 and navigate to the "Quiz" page.

## 📖 How to Use

### 1. Start Quiz
- Click "🚀 Start Quiz" button
- Backend creates a session with 30 random questions from questions.json

### 2. Answer Questions
- Read the question carefully
- Select one of 4 options (A, B, C, D)
- Click "Submit Answer"
- View feedback and progress

### 3. Complete Quiz
- After answering all 30 questions, quiz auto-completes
- System calculates score immediately

### 4. View Results
- Overall score (percentage)
- Pass/Fail status (75% = passing grade)
- Detailed review of each question:
  - Your answer vs. correct answer
  - Explanation (if available)
  - Question difficulty and category

## 📊 Question Format

### Input Format (questions.json)
```json
[
  {
    "question": "What is the capital of France?",
    "options": [
      "a) Berlin",
      "b) London",
      "c) Paris",
      "d) Madrid"
    ],
    "correct_answer": "c",
    "bloom_level": "C1",
    "unit": "J.620100.005.02",
    "explanation": "Paris is the capital of France."
  }
]
```

### How Backend Transforms It
1. Parses array format directly
2. Removes option prefixes ("a) ", "b) ", etc.)
3. Maps "correct_answer" letter to index
4. Creates Choice objects with IDs: A, B, C, D
5. Extracts category from "unit" field
6. Maps "bloom_level" to difficulty (easy/medium/hard)

### API Response Format
```json
{
  "id": "q1",
  "question_text": "What is the capital of France?",
  "category": "02",
  "difficulty": "easy",
  "choices": [
    {"id": "A", "text": "Berlin"},
    {"id": "B", "text": "London"},
    {"id": "C", "text": "Paris"},
    {"id": "D", "text": "Madrid"}
  ],
  "answer_type": "multiple_choice"
}
```

See `FORMAT_TRANSFORMATION_REFERENCE.md` for detailed examples.

## 🔌 API Endpoints

### Quiz Endpoints

#### 1. Start Quiz
```
POST /api/quiz/start
Response:
{
  "success": true,
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "total_questions": 30,
  "first_question": { ... }
}
```

#### 2. Get Question
```
GET /api/quiz/question/{session_id}/{question_index}
Response:
{
  "success": true,
  "question_index": 0,
  "question": { ... },
  "progress": { ... }
}
```

#### 3. Submit Answer
```
POST /api/quiz/submit-answer
Request:
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "question_id": "q1",
  "choice_id": "C"
}
Response:
{
  "success": true,
  "is_correct": true
}
```

#### 4. Get Progress
```
GET /api/quiz/progress/{session_id}
Response:
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

#### 5. Complete Quiz
```
POST /api/quiz/complete/{session_id}
Response:
{
  "success": true,
  "results": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "total_questions": 30,
    "correct_answers": 23,
    "wrong_answers": 7,
    "score_percentage": 76.67,
    "is_passed": true,
    "answers": [ ... ]
  }
}
```

#### 6. Get Results
```
GET /api/quiz/results/{session_id}
Response:
{
  "success": true,
  "results": { ... }
}
```

#### 7. Get All Results
```
GET /api/quiz/all-results
Response:
{
  "success": true,
  "results": [ ... ]
}
```

#### 8. Results Summary
```
GET /api/quiz/results-summary
Response:
{
  "success": true,
  "summary": {
    "total_attempts": 5,
    "passed": 3,
    "failed": 2,
    "average_score": 72.5
  }
}
```

#### 9. Health Check
```
GET /api/quiz/health
Response:
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00"
}
```

## ⚙️ Configuration

### Backend (app.py)
- Flask runs on `http://127.0.0.1:5000/`
- CORS enabled for frontend communication
- Questions loaded from `backend/data/` directory
- Results stored in `backend/storage/` directory

### Frontend (config.py)
```python
backend_endpoint = "http://127.0.0.1:5000/"
use_mock_data = False
use_search = False
```

### Frontend (main.py)
```python
PAGES_BEFORE_ONBOARDING = {
    "Quiz": "pages/quiz.py",
    "My Profile": "pages/learner_profile.py",
    "Learning Path": "pages/learning_path.py"
}

PAGES_AFTER_ONBOARDING = {
    "Quiz": "pages/quiz.py",
    "Dashboard": "pages/dashboard.py",
    "Learning Path": "pages/learning_path.py",
    "My Profile": "pages/learner_profile.py"
}
```

## 🧪 Testing

### Test Backend Health
```bash
curl http://127.0.0.1:5000/api/quiz/health
```

### Test Start Quiz
```bash
curl -X POST http://127.0.0.1:5000/api/quiz/start
```

### Test Complete Flow (in Frontend)
1. Click "Quiz" in navigation
2. Click "🚀 Start Quiz"
3. Answer all questions
4. View results

See `TESTING_BACKEND_FIX.md` for comprehensive testing guide with validation checklist.

## 🐛 Troubleshooting

### Backend Won't Start
**Problem**: ImportError or connection refused
**Solutions**:
1. Check Python version: `python --version` (needs 3.9+)
2. Install requirements: `pip install -r requirements.txt`
3. Check port 5000 is not in use: `netstat -an | grep 5000`
4. Run with python3: `python3 app.py` (if python doesn't work)

### Frontend Can't Connect to Backend
**Problem**: "Connection refused" in quiz error
**Solutions**:
1. Verify backend is running: Check for Flask output in terminal
2. Check endpoint: Verify `backend_endpoint` in `frontend/config.py`
3. Check CORS: Verify CORS is enabled in `backend/app.py`
4. Check firewall: Ensure port 5000 is accessible

### Quiz Returns 400 Error
**Problem**: "POST /api/quiz/start HTTP/1.1 400"
**Solutions**:
1. Check questions.json exists: `backend/data/extracted_refined_generated_questions_fewshot_perunit_*.json`
2. Check JSON format: Should be `[{...}, {...}]` not `{"questions": [...]}`
3. Check backend logs for specific error
4. Verify question_loader.py imports from `models.model` (not `types.models`)

### Quiz Doesn't Calculate Score Correctly
**Problem**: Score not 75% or calculation seems wrong
**Solutions**:
1. Verify pass threshold: Check `PASSING_PERCENTAGE = 75` in session_manager.py
2. Verify scoring formula: Score = (correct / 30) × 100
3. Check that 23+ out of 30 is needed to pass
4. Review detailed answer review in results to identify scoring issue

### Import Errors
**Problem**: "cannot import name 'GenericAlias' from 'types'"
**Solution**: 
- Confirmed fixed - backend/types/ renamed to backend/models/
- Verify no old imports with `grep -r "from types.models" backend/`

## 📝 Recent Fixes

### Backend Format Compatibility (Latest)
**Issue**: 400 error when starting quiz
**Fix**: Updated question_loader.py to parse questions.json as array format (not wrapped object)
**Status**: ✅ COMPLETE - See BACKEND_FIX_SUMMARY.md

### Navigation Menu Ordering (Previous)
**Issue**: Menu items not respecting order from main.py
**Fix**: Switched from st.navigation() to custom st.radio() navigation
**Status**: ✅ COMPLETE

### Import Shadowing (Earlier)
**Issue**: ImportError with types module
**Fix**: Renamed backend/types/ → backend/models/
**Status**: ✅ COMPLETE

## 📚 Documentation

- [BACKEND_FIX_SUMMARY.md](BACKEND_FIX_SUMMARY.md) - What was fixed and why
- [TESTING_BACKEND_FIX.md](TESTING_BACKEND_FIX.md) - Complete testing guide
- [FORMAT_TRANSFORMATION_REFERENCE.md](FORMAT_TRANSFORMATION_REFERENCE.md) - Data format details
- Backend README: [backend/README.md](backend/README.md)
- Frontend README: [frontend/README.md](frontend/README.md)

## 🎓 Learning Resources

### Bloom's Taxonomy Levels (in bloom_level field)
- **C1, C2**: Easy (Remember, Understand)
- **C3, C4**: Medium (Apply, Analyze)
- **C5, C6**: Hard (Evaluate, Create)

### Question Categories (from unit field)
- Categories are extracted from the last segment of the unit path
- Example: "J.620100.005.02" → category "02"

### Scoring
- Total questions: 30
- Passing score: 75% = 23 correct answers minimum
- Score calculation: (correct / 30) × 100

## ✨ Features

- ✅ 30-question randomized quiz
- ✅ Multiple choice with 4 options each
- ✅ Real-time progress tracking
- ✅ Automatic pass/fail determination (75% threshold)
- ✅ Detailed results with answer review
- ✅ Question explanation display
- ✅ Category and difficulty tracking
- ✅ Result persistence
- ✅ Beautiful Streamlit UI
- ✅ RESTful Flask API
- ✅ CORS-enabled for cross-origin requests

## 🔐 Future Enhancements

- [ ] User authentication and profiles
- [ ] Quiz history and analytics
- [ ] Timed quizzes
- [ ] Different difficulty levels
- [ ] Question bank management UI
- [ ] Performance analytics dashboard
- [ ] Email score notifications
- [ ] Mobile-friendly responsive design

## 📄 License

See LICENSE file for details.

## 👥 Support

For issues or questions:
1. Check troubleshooting section above
2. Review documentation files
3. Check backend logs for error details
4. Verify all dependencies are installed

---

**Last Updated**: Today
**Status**: ✅ Ready to Use
**Backend Fix**: ✅ Complete - questions.json array format now supported
