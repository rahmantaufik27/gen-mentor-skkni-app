#!/usr/bin/env python3
"""Test the complete quiz flow end-to-end."""

import sys
sys.path.insert(0, '.')

from services.question_loader import QuestionLoader
from services.quiz_service import QuizService
from config.database import execute_query
from uuid import uuid4

# Create a test user first
user_id = str(uuid4())
unique_email = f"test{user_id[:8]}@example.com"

insert_user = 'INSERT INTO users (id, full_name, email, password_hash) VALUES (%s, %s, %s, %s)'
try:
    execute_query(
        insert_user,
        (
            user_id,
            'Test User',
            unique_email,
            'hashedpassword123'
        )
    )
    print(f"Test user created: {user_id[:8]}...")
except Exception as e:
    error_str = str(e)
    if 'duplicate' in error_str or 'already exists' in error_str:
        print(f"Using existing test user")
    else:
        print(f"Error creating test user: {e}")
        sys.exit(1)

print("="*70)
print("TESTING COMPLETE QUIZ FLOW")
print("="*70)

# Initialize services
loader = QuestionLoader('data')
service = QuizService(loader)

# Test 1: Start Quiz
print("\n[1/3] Starting quiz...")
start_response = service.start_quiz(user_id)
if not start_response.get("success"):
    error = start_response.get('error')
    print(f"✗ FAILED: {error}")
    sys.exit(1)

print("✓ Quiz started successfully")
session_id = start_response['session_id']
total_questions = start_response['total_questions']
print(f"   Session ID: {session_id[:8]}...")
print(f"   Total Questions: {total_questions}")

# Test 2: Answer all questions
print(f"\n[2/3] Answering all {total_questions} questions...")
for i in range(total_questions):
    # Get question
    q_resp = service.get_question(session_id, i)
    if not q_resp.get("success"):
        print(f"✗ Failed to get question {i+1}")
        sys.exit(1)
    
    # Get first choice as answer
    choices = q_resp.get("choices", [])
    if not choices:
        print(f"✗ No choices for question {i+1}")
        sys.exit(1)
    
    first_choice = choices[0]['id']
    
    # Submit answer
    submit_resp = service.submit_answer(session_id, i, first_choice)
    if not submit_resp.get("success"):
        error = submit_resp.get('error')
        print(f"✗ Failed to submit answer for question {i+1}: {error}")
        sys.exit(1)
    
    if (i + 1) % 6 == 0:
        print(f"   ✓ Answered questions 1-{i+1}")

# Test 3: Complete quiz
print(f"\n[3/3] Completing quiz...")
complete_resp = service.complete_quiz(session_id, user_id)
if not complete_resp.get("success"):
    error = complete_resp.get('error')
    print(f"✗ FAILED: {error}")
    sys.exit(1)

print("✓ Quiz completed successfully!")
attempt_id = complete_resp.get('attempt_id', '')[:8]
total_score = complete_resp.get('total_score')
correct = complete_resp.get('correct_answers')
total = complete_resp.get('total_questions')
status = 'PASSED' if complete_resp.get('is_passed') else 'FAILED'

print(f"   Attempt ID: {attempt_id}...")
print(f"   Total Score: {total_score}")
print(f"   Correct Answers: {correct}/{total}")
print(f"   Status: {status}")

unit_mastery = complete_resp.get('unit_mastery', {})
print(f"\n   Unit Mastery:")
for unit, data in sorted(unit_mastery.items()):
    is_mastered = data.get('is_mastered')
    unit_status = "MASTERED" if is_mastered else "REMEDIAL"
    score = data.get('score')
    print(f"      {unit}: {score}/21 - {unit_status}")

print("\n" + "="*70)
print("✓ ALL TESTS PASSED")
print("="*70)
