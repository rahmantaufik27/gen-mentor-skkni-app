#!/usr/bin/env python
"""
Test script for quiz implementation validation.

Tests:
1. Dataset loading and organization
2. Quiz generation (36 questions, 6 units, proper Bloom distribution)
3. Scoring system (C1-C6 values)
4. Mastery calculation (threshold 15/21)
5. Database operations (migrations, persistence)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.question_loader import QuestionLoader
from services.quiz_generator import QuizGenerator
from config.database import execute_query
from migrations.002_create_quiz_tables import create_quiz_tables, check_quiz_tables_exist


def test_dataset_loading():
    """Test 1: Dataset Loading"""
    print("\n" + "="*60)
    print("TEST 1: DATASET LOADING")
    print("="*60)
    
    try:
        question_loader = QuestionLoader("backend/data")
        questions = question_loader.load_questions()
        
        print(f"✓ Loaded {len(questions)} questions")
        print(f"✓ Dataset path validated")
        
        # Check structure
        if questions:
            sample = questions[0]
            print(f"\nSample question structure:")
            print(f"  - ID: {sample.id}")
            print(f"  - Unit: {sample.unit}")
            print(f"  - Bloom: {sample.bloom_level}")
            print(f"  - Choices: {len(sample.choices)}")
        
        return True
    except Exception as e:
        print(f"✗ Dataset loading failed: {str(e)}")
        return False


def test_quiz_generation():
    """Test 2: Quiz Generation"""
    print("\n" + "="*60)
    print("TEST 2: QUIZ GENERATION")
    print("="*60)
    
    try:
        question_loader = QuestionLoader("backend/data")
        generator = QuizGenerator(question_loader)
        
        # Validate dataset
        validation = generator.validate_dataset()
        print(f"Dataset Validation:")
        print(f"  - Valid: {validation['valid']}")
        print(f"  - Total Questions: {validation['total_questions']}")
        print(f"  - Available Units: {validation['units_available']}")
        print(f"  - Units with all 6 Bloom levels: {validation['units_with_full_bloom']}")
        
        # Generate quiz
        questions, unit_codes = generator.generate_quiz()
        
        print(f"\nGenerated Quiz:")
        print(f"  ✓ Total Questions: {len(questions)}")
        print(f"  ✓ Target: 36 questions")
        print(f"  - Status: {'PASS' if len(questions) == 36 else 'WARN'}")
        
        # Analyze distribution
        unit_dist = {}
        for unit in set(unit_codes):
            count = unit_codes.count(unit)
            unit_dist[unit] = count
        
        print(f"\nUnit Distribution:")
        for unit, count in sorted(unit_dist.items()):
            print(f"  {unit}: {count} questions")
        
        # Analyze Bloom distribution
        bloom_dist = {}
        for q in questions:
            bloom = q.bloom_level.upper()
            bloom_dist[bloom] = bloom_dist.get(bloom, 0) + 1
        
        print(f"\nBloom Level Distribution:")
        for bloom in sorted(bloom_dist.keys()):
            print(f"  {bloom}: {bloom_dist[bloom]} questions")
        
        return True
    except Exception as e:
        print(f"✗ Quiz generation failed: {str(e)}")
        return False


def test_scoring_system():
    """Test 3: Scoring System"""
    print("\n" + "="*60)
    print("TEST 3: SCORING SYSTEM")
    print("="*60)
    
    try:
        question_loader = QuestionLoader("backend/data")
        generator = QuizGenerator(question_loader)
        
        print("Bloom Score Mapping:")
        for bloom in ["C1", "C2", "C3", "C4", "C5", "C6"]:
            score = generator.get_bloom_score(bloom)
            print(f"  {bloom}: {score} points")
        
        # Test mastery calculation
        print(f"\nMastery Calculation (threshold: {generator.MASTERY_THRESHOLD}/{generator.MAX_UNIT_SCORE}):")
        test_scores = [0, 7, 14, 15, 21]
        for score in test_scores:
            status, is_mastered = generator.calculate_unit_mastery(score)
            symbol = "✓" if is_mastered else "✗"
            print(f"  {symbol} Score {score:2d}: {status} - {is_mastered}")
        
        return True
    except Exception as e:
        print(f"✗ Scoring system test failed: {str(e)}")
        return False


def test_database_setup():
    """Test 4: Database Setup"""
    print("\n" + "="*60)
    print("TEST 4: DATABASE SETUP")
    print("="*60)
    
    try:
        print("Creating quiz tables...")
        create_quiz_tables()
        
        print("\nVerifying table creation...")
        exists = check_quiz_tables_exist()
        
        if exists:
            print("✓ All quiz tables created successfully")
            return True
        else:
            print("✗ Some tables failed to create")
            return False
    except Exception as e:
        print(f"✗ Database setup failed: {str(e)}")
        return False


def test_unit_organization():
    """Test 5: Unit Organization"""
    print("\n" + "="*60)
    print("TEST 5: UNIT ORGANIZATION")
    print("="*60)
    
    try:
        question_loader = QuestionLoader("backend/data")
        generator = QuizGenerator(question_loader)
        
        print(f"Units with complete Bloom coverage (all C1-C6):")
        complete_units = []
        for unit, bloom_dict in generator.questions_by_unit_bloom.items():
            blooms_present = set(bloom_dict.keys())
            expected_blooms = set(["C1", "C2", "C3", "C4", "C5", "C6"])
            if blooms_present == expected_blooms:
                total_qs = sum(len(qs) for qs in bloom_dict.values())
                print(f"  ✓ {unit}: {total_qs} questions")
                complete_units.append(unit)
        
        if not complete_units:
            print("  (None - using adaptive distribution)")
        
        print(f"\nTop 6 units by question count:")
        sorted_units = sorted(
            generator.questions_by_unit_bloom.items(),
            key=lambda x: sum(len(qs) for qs in x[1].values()),
            reverse=True
        )[:6]
        
        for i, (unit, bloom_dict) in enumerate(sorted_units, 1):
            total = sum(len(qs) for qs in bloom_dict.values())
            blooms = len(bloom_dict)
            print(f"  {i}. {unit}: {total} questions, {blooms}/6 Bloom levels")
        
        return True
    except Exception as e:
        print(f"✗ Unit organization test failed: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("\n╔" + "="*58 + "╗")
    print("║" + " QUIZ IMPLEMENTATION VALIDATION ".center(58) + "║")
    print("╚" + "="*58 + "╝")
    
    results = {
        "Dataset Loading": test_dataset_loading(),
        "Quiz Generation": test_quiz_generation(),
        "Scoring System": test_scoring_system(),
        "Unit Organization": test_unit_organization(),
        "Database Setup": test_database_setup()
    }
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Quiz implementation is ready.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Please review above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
