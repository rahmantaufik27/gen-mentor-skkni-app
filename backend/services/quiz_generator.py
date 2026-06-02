"""
Service for generating and managing quizzes with specific requirements.

Quiz Rules:
- 36 questions total
- 6 units
- Each unit has exactly 6 questions (one per Bloom level C1-C6)
- Questions selected randomly
- Scoring: Bloom level value (C1=1, C2=2, ... C6=6)
- Unit mastery: Score >= 15 out of 21 max per unit
"""

import random
from typing import List, Dict, Optional, Tuple
from collections import defaultdict
from services.question_loader import QuestionLoader
from models.model import Question


class QuizGenerator:
    """Generate quizzes with specific structure: 6 units × 6 Bloom levels = 36 questions"""
    
    # Score mapping: Bloom level to points
    BLOOM_SCORES = {
        "C1": 1,
        "C2": 2,
        "C3": 3,
        "C4": 4,
        "C5": 5,
        "C6": 6
    }
    
    # Mastery threshold: 15 points out of 21 per unit
    MASTERY_THRESHOLD = 15
    MAX_UNIT_SCORE = 21  # 6 questions × max 3.5 average, but we use exact Bloom scores
    
    # Top 6 units by question count (these have best Bloom coverage)
    PREFERRED_UNITS = [
        "J.620100.010",
        "J.620100.016",
        "J.620100.005",
        "J.620100.019",
        "J.620100.015",
        "J.620100.017"
    ]
    
    BLOOM_LEVELS = ["C1", "C2", "C3", "C4", "C5", "C6"]
    
    def __init__(self, question_loader: QuestionLoader):
        """
        Initialize quiz generator
        
        Args:
            question_loader: QuestionLoader instance
        """
        self.question_loader = question_loader
        self._organize_questions_by_unit_and_bloom()
    
    def _organize_questions_by_unit_and_bloom(self):
        """Organize questions by unit and Bloom level for quick access."""
        self.questions_by_unit_bloom = defaultdict(lambda: defaultdict(list))
        
        all_questions = self.question_loader.load_questions()
        
        for question in all_questions:
            unit = question.unit
            bloom = question.bloom_level.upper()
            
            # Extract main unit code (e.g., "J.620100.010" from "J.620100.010.02")
            unit_parts = unit.split(".")
            if len(unit_parts) >= 3:
                main_unit = ".".join(unit_parts[:3])
            else:
                main_unit = unit
            
            self.questions_by_unit_bloom[main_unit][bloom].append(question)
    
    def generate_quiz(self) -> Tuple[List[Question], List[str]]:
        """
        Generate a complete quiz with 36 questions from 6 units.
        
        Each unit gets exactly 6 questions (one per Bloom level when available).
        If a unit lacks a Bloom level, that question is skipped for that unit.
        
        Returns:
            Tuple of (list of Question objects, list of unit codes for each question)
            
        Raises:
            ValueError: If insufficient questions available for quiz generation
        """
        quiz_questions = []
        quiz_unit_codes = []
        
        # Use preferred units if they have enough coverage
        units_to_use = []
        for unit in self.PREFERRED_UNITS:
            if unit in self.questions_by_unit_bloom:
                units_to_use.append(unit)
            if len(units_to_use) >= 6:
                break
        
        if len(units_to_use) < 6:
            raise ValueError(
                f"Insufficient units with questions. Found {len(units_to_use)}, need 6. "
                "Dataset must have questions organized by unit codes."
            )
        
        # Generate 6 questions per unit (one per Bloom level)
        for unit_code in units_to_use:
            unit_questions = []
            
            # Try to get one question per Bloom level
            for bloom_level in self.BLOOM_LEVELS:
                available = self.questions_by_unit_bloom[unit_code][bloom_level]
                
                if available:
                    # Randomly select one question from this unit/bloom combination
                    selected_question = random.choice(available)
                    unit_questions.append(selected_question)
            
            # Ensure we have exactly 6 questions per unit
            # If we have fewer Bloom levels available, pad with random questions from unit
            if len(unit_questions) < 6:
                # Get all remaining questions from unit
                all_unit_questions = []
                for bloom_qs in self.questions_by_unit_bloom[unit_code].values():
                    all_unit_questions.extend(bloom_qs)
                
                # Remove already selected ones
                remaining = [q for q in all_unit_questions if q not in unit_questions]
                
                # Add random questions to reach 6
                needed = 6 - len(unit_questions)
                if len(remaining) >= needed:
                    unit_questions.extend(random.sample(remaining, needed))
                else:
                    unit_questions.extend(remaining)
            
            # Ensure exactly 6 by slicing if needed
            unit_questions = unit_questions[:6]
            
            quiz_questions.extend(unit_questions)
            quiz_unit_codes.extend([unit_code] * len(unit_questions))
        
        if len(quiz_questions) < 36:
            raise ValueError(
                f"Could not generate 36-question quiz. Generated {len(quiz_questions)} questions. "
                "Check dataset has sufficient questions per unit."
            )
        
        return quiz_questions, quiz_unit_codes
    
    def get_bloom_score(self, bloom_level: str) -> int:
        """
        Get score for a Bloom level.
        
        Args:
            bloom_level: Bloom level (C1-C6)
            
        Returns:
            Score points for that level
        """
        return self.BLOOM_SCORES.get(bloom_level.upper(), 0)
    
    def calculate_unit_mastery(self, unit_score: int) -> Tuple[str, bool]:
        """
        Calculate mastery status for a unit.
        
        Args:
            unit_score: Total score for unit (0-21)
            
        Returns:
            Tuple of (status string, is_mastered boolean)
        """
        if unit_score >= self.MASTERY_THRESHOLD:
            return "MASTERED", True
        else:
            return "REMEDIAL", False
    
    def validate_dataset(self) -> Dict[str, any]:
        """
        Validate that dataset has sufficient data for quiz generation.
        
        Returns:
            Dictionary with validation results and recommendations
        """
        validation = {
            "valid": True,
            "total_questions": len(self.question_loader.load_questions()),
            "units_available": len(self.questions_by_unit_bloom),
            "units_with_full_bloom": 0,
            "unit_coverage": {}
        }
        
        # Check each unit's Bloom coverage
        for unit, blooms in self.questions_by_unit_bloom.items():
            covered_blooms = len(blooms)
            has_all = all(level in blooms for level in self.BLOOM_LEVELS)
            
            validation["unit_coverage"][unit] = {
                "questions": sum(len(qs) for qs in blooms.values()),
                "bloom_levels": covered_blooms,
                "has_all_6_blooms": has_all
            }
            
            if has_all:
                validation["units_with_full_bloom"] += 1
        
        # Dataset is valid if we have at least 6 units
        validation["valid"] = len(self.questions_by_unit_bloom) >= 6
        
        return validation
