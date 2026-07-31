"""
Type definitions and models for the quiz application.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import json
from datetime import datetime


class AnswerType(str, Enum):
    """Types of answers"""
    MULTIPLE_CHOICE = "multiple_choice"
    TRUE_FALSE = "true_false"


@dataclass
class Choice:
    """Answer choice model"""
    id: str
    text: str
    is_correct: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Question:
    """Question model"""
    id: str
    question_text: str
    category: str
    difficulty: str
    choices: List[Choice]
    explanation: str
    unit: str = ""  # e.g., "J.620100.005.02"
    bloom_level: str = ""  # e.g., "C3"
    answer_type: str = AnswerType.MULTIPLE_CHOICE.value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "question_text": self.question_text,
            "category": self.category,
            "difficulty": self.difficulty,
            "choices": [c.to_dict() for c in self.choices],
            "explanation": self.explanation,
            "unit": self.unit,
            "bloom_level": self.bloom_level,
            "answer_type": self.answer_type,
        }


@dataclass
class UserAnswer:
    """User answer model"""
    question_id: str
    selected_choice_id: str
    is_correct: bool
    answered_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QuizSession:
    """Quiz session model"""
    session_id: str
    questions: List[Question]
    user_answers: List[UserAnswer]
    started_at: str
    completed_at: Optional[str] = None
    is_completed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "questions": [q.to_dict() for q in self.questions],
            "user_answers": [a.to_dict() for a in self.user_answers],
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "is_completed": self.is_completed,
        }


@dataclass
class QuizResult:
    """Quiz result model"""
    session_id: str
    total_questions: int
    correct_answers: int
    wrong_answers: int
    score_percentage: float
    is_passed: bool
    completed_at: str
    answers: List[Dict[str, Any]]  # Detailed answer review

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
