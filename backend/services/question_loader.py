"""
Service for loading and managing question datasets.
"""

import json
import os
from typing import List, Dict, Any
from models.model import Question, Choice, AnswerType


class QuestionLoader:
    """Loader for question datasets from JSON files"""

    def __init__(self, data_dir: str):
        """
        Initialize question loader
        
        Args:
            data_dir: Path to data directory containing JSON files
        """
        self.data_dir = data_dir
        self.questions_cache = None

    def load_questions(self) -> List[Question]:
        """
        Load questions from questions.json
        
        Returns:
            List of Question objects
        """
        if self.questions_cache:
            return self.questions_cache

        questions_path = os.path.join(self.data_dir, "questions.json")
        
        if not os.path.exists(questions_path):
            raise FileNotFoundError(f"Questions file not found: {questions_path}")

        with open(questions_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        questions = []
        for idx, q_data in enumerate(data):
            # Extract correct answer letter (a, b, c, d)
            correct_answer = str(q_data.get("correct_answer", "")).upper().strip(")")
            
            # Map letter to index
            letter_to_index = {"A": 0, "B": 1, "C": 2, "D": 3, "a": 0, "b": 1, "c": 2, "d": 3}
            correct_idx = letter_to_index.get(correct_answer, 0)
            
            # Parse options and build choices
            options = q_data.get("options", [])
            choices = []
            
            for choice_idx, option_text in enumerate(options):
                # Clean option text (remove "a) ", "b) ", etc.)
                clean_text = option_text.strip()
                if len(clean_text) > 2 and clean_text[1] in [")", "."]:
                    clean_text = clean_text[3:].strip()
                elif len(clean_text) > 3 and clean_text[1:3] == ") ":
                    clean_text = clean_text[3:].strip()
                
                choice = Choice(
                    id=chr(65 + choice_idx),  # A, B, C, D
                    text=clean_text,
                    is_correct=(choice_idx == correct_idx)
                )
                choices.append(choice)
            
            # Extract category from unit
            category = q_data.get("unit", "General").split(".")[-1] if q_data.get("unit") else "General"
            
            # Map bloom level to difficulty
            bloom = str(q_data.get("bloom_level", "C2")).upper()
            if bloom.startswith("C1") or bloom.startswith("C2"):
                difficulty = "easy"
            elif bloom.startswith("C3") or bloom.startswith("C4"):
                difficulty = "medium"
            else:
                difficulty = "hard"

            question = Question(
                id=f"q{idx+1}",
                question_text=q_data.get("question", ""),
                category=category,
                difficulty=difficulty,
                choices=choices,
                explanation=q_data.get("explanation", ""),
                answer_type=AnswerType.MULTIPLE_CHOICE.value
            )
            questions.append(question)

        self.questions_cache = questions
        return questions

    def get_question_by_id(self, question_id: str) -> Question:
        """
        Get a specific question by ID
        
        Args:
            question_id: ID of the question
            
        Returns:
            Question object or None if not found
        """
        questions = self.load_questions()
        for question in questions:
            if question.id == question_id:
                return question
        return None

    def get_questions_by_category(self, category: str) -> List[Question]:
        """
        Get questions filtered by category
        
        Args:
            category: Category name
            
        Returns:
            List of questions in the category
        """
        questions = self.load_questions()
        return [q for q in questions if q.category.lower() == category.lower()]

    def get_all_categories(self) -> List[str]:
        """
        Get all unique categories
        
        Returns:
            List of category names
        """
        questions = self.load_questions()
        categories = set(q.category for q in questions)
        return sorted(list(categories))

    def validate_question_answer(self, question_id: str, choice_id: str) -> bool:
        """
        Validate if a chosen answer is correct
        
        Args:
            question_id: ID of the question
            choice_id: ID of the chosen choice
            
        Returns:
            True if answer is correct, False otherwise
        """
        question = self.get_question_by_id(question_id)
        if not question:
            return False

        for choice in question.choices:
            if choice.id == choice_id:
                return choice.is_correct

        return False
