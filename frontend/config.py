"""Frontend configuration - global constants read across pages/utils."""

backend_endpoint = "http://127.0.0.1:5000/"  # Flask API base URL (trailing slash required)
use_mock_data = True  # LLM-pipeline features fall back to local JSON fixtures instead of calling the backend
use_search = True  # enables search-related LLM features (unused by the auth/quiz/mastery flow)
showPagesInSidebar = False  # kept for reference; the app's own sidebar nav (utils/theme.py) is used instead
