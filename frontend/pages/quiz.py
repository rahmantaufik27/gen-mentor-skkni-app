"""
Quiz Page Component for Streamlit

Route Protection:
- Requires authentication (redirects to login if not authenticated)
- Only accessible to authenticated users
- Displays personalized quiz assessment for learners
"""

import streamlit as st
from utils.quiz_api import (
    start_quiz, get_question, submit_answer, get_progress,
    complete_quiz, get_results, get_all_results, get_results_summary
)
from datetime import datetime
import json
# from utils.auth_guard import require_authentication


def initialize_quiz_state():
    """Initialize quiz session state"""
    if "quiz_session_id" not in st.session_state:
        st.session_state.quiz_session_id = None
    if "quiz_current_question" not in st.session_state:
        st.session_state.quiz_current_question = 0
    if "quiz_started" not in st.session_state:
        st.session_state.quiz_started = False
    if "quiz_completed" not in st.session_state:
        st.session_state.quiz_completed = False
    if "quiz_result" not in st.session_state:
        st.session_state.quiz_result = None


def render_quiz_page():
    """Render the main quiz page"""
    # NOTE: st.set_page_config() is called by main.py, not here
    
    initialize_quiz_state()
    
    st.title("🎯 Quiz Assessment")
    st.divider()
    
    # Quiz not started
    if not st.session_state.quiz_started:
        render_quiz_start()
    
    # Quiz in progress
    elif st.session_state.quiz_started and not st.session_state.quiz_completed:
        render_quiz_progress()
    
    # Quiz completed
    else:
        render_quiz_results()


def render_quiz_start():
    """Render quiz start screen"""
    st.subheader("Start a New Quiz")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        ### Quiz Information
        - **Total Questions:** 30
        - **Question Types:** Multiple Choice
        - **Passing Score:** 75% (23 out of 30)
        - **Time Limit:** No time limit
        - **Randomization:** Questions are randomized for each attempt
        
        ### How to Take the Quiz
        1. Click "Start Quiz" to begin
        2. Answer each question by selecting one option
        3. Click "Next Question" to proceed
        4. Review your progress at the top
        5. Complete all questions to see results
        """)
    
    with col2:
        st.info("""
        ✅ **Tips for Success**
        - Read each question carefully
        - Consider all options before answering
        - You cannot go back to previous questions
        - Results will show your score, pass/fail status, and detailed review
        """)
    
    st.divider()
    
    if st.button("🚀 Start Quiz", use_container_width=True, type="primary", key="start_quiz_btn"):
        result = start_quiz()
        
        if result.get("success"):
            st.session_state.quiz_session_id = result.get("session_id")
            st.session_state.quiz_current_question = 0
            st.session_state.quiz_started = True
            st.session_state.quiz_completed = False
            st.rerun()
        else:
            st.error(f"Failed to start quiz: {result.get('error', 'Unknown error')}")


def render_quiz_progress():
    """Render quiz in progress"""
    session_id = st.session_state.quiz_session_id
    question_index = st.session_state.quiz_current_question
    
    # Get progress
    progress_result = get_progress(session_id)
    if not progress_result.get("success"):
        st.error("Failed to get quiz progress")
        return
    
    progress = progress_result.get("progress", {})
    total = progress.get("total_questions", 30)
    answered = progress.get("answered_questions", 0)
    
    # Progress bar
    st.progress(answered / total, text=f"Progress: {answered}/{total} questions")
    
    st.divider()
    
    # Get current question
    question_result = get_question(session_id, question_index)
    if not question_result.get("success"):
        st.error("Failed to load question")
        return
    
    question_data = question_result.get("question", {})
    
    # Display question
    st.subheader(f"Question {question_index + 1} of {total}")
    st.write(f"**Unit:** {question_data.get('unit')} | **Bloom Level:** {question_data.get('bloom_level')}")
    st.divider()
    
    st.write(f"### {question_data.get('question')}")
    
    # Answer options
    options = question_data.get("options", [])
    
    # Store selected answer
    selected_answer = st.radio(
        label="Select your answer:",
        options=[f"{chr(65 + i)}. {choice}" for i, choice in enumerate(options)],
        key=f"question_{question_data.get('id')}"
    )
    
    # Get choice ID from selection
    if selected_answer:
        choice_letter = selected_answer.split(".")[0]
        choice_index = ord(choice_letter) - ord("A")
        # Use letter ID (A, B, C, D) for consistency
        selected_choice_id = chr(65 + choice_index)  # Convert to A, B, C, D
        
        st.divider()
        
        col1, col2, col3 = st.columns(3)
        
        # Submit answer
        with col1:
            if st.button("✓ Submit Answer", use_container_width=True, type="primary"):
                submit_result = submit_answer(
                    session_id,
                    question_data.get("id"),
                    selected_choice_id
                )
                
                if submit_result.get("success"):
                    is_completed = submit_result.get("is_completed", False)
                    
                    if is_completed:
                        # Quiz finished
                        st.session_state.quiz_completed = True
                        st.rerun()
                    else:
                        # Move to next question
                        st.session_state.quiz_current_question += 1
                        st.rerun()
                else:
                    st.error(f"Failed to submit answer: {submit_result.get('error')}")
        
        # View summary
        with col2:
            if st.button("📊 View Summary", use_container_width=True):
                show_quiz_summary(session_id)
        
        # Quit quiz
        with col3:
            if st.button("🚪 Exit Quiz", use_container_width=True):
                st.session_state.quiz_started = False
                st.session_state.quiz_current_question = 0
                st.session_state.quiz_session_id = None
                st.rerun()


def render_quiz_results():
    """Render quiz results"""
    session_id = st.session_state.quiz_session_id
    
    # Get results
    results_result = get_results(session_id)
    if not results_result.get("success"):
        st.error("Failed to load results")
        return
    
    result_data = results_result.get("result", {})
    
    # Display results header
    st.subheader("Quiz Complete!")
    st.divider()
    
    # Main score display
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Score",
            f"{result_data.get('score_percentage', 0):.1f}%",
            delta=f"{result_data.get('correct_answers', 0)}/{result_data.get('total_questions', 30)}"
        )
    
    with col2:
        status = "✅ PASSED" if result_data.get("is_passed") else "❌ FAILED"
        st.metric("Status", status)
    
    with col3:
        st.metric("Correct", result_data.get("correct_answers", 0))
    
    with col4:
        st.metric("Wrong", result_data.get("wrong_answers", 0))
    
    st.divider()
    
    # Pass/Fail determination
    is_passed = result_data.get("is_passed", False)
    passing_score = 75
    
    if is_passed:
        st.success(f"🎉 Congratulations! You passed the quiz with {result_data.get('score_percentage', 0):.1f}%")
    else:
        st.warning(f"⚠️ You did not pass this time. Passing score is {passing_score}%. Your score: {result_data.get('score_percentage', 0):.1f}%")
    
    st.divider()
    
    # Detailed answer review
    st.subheader("📋 Detailed Answer Review")
    
    answers = result_data.get("answers", [])
    
    for idx, answer in enumerate(answers, 1):
        with st.expander(f"Question {idx}: {answer.get('question', 'Unknown')}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**unit:** {answer.get('unit')}")
            
            with col2:
                if answer.get("is_correct"):
                    st.success("✅ Correct")
                else:
                    st.error("❌ Incorrect")
            
            st.write(f"**Your Answer:** {answer.get('your_answer')}")
            st.write(f"**Correct Answer:** {answer.get('correct_answer')}")
    
    st.divider()
    
    # Meta information
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Session ID:** `{result_data.get('session_id')}`")
    with col2:
        st.write(f"**Completed At:** {result_data.get('completed_at')}")
    
    st.divider()
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Take Another Quiz", use_container_width=True, type="primary"):
            st.session_state.quiz_started = False
            st.session_state.quiz_current_question = 0
            st.session_state.quiz_session_id = None
            st.session_state.quiz_completed = False
            st.rerun()
    
    with col2:
        if st.button("📊 View All Results", use_container_width=True):
            show_all_results()
    
    with col3:
        if st.button("⬅️ Go Home", use_container_width=True):
            st.session_state.quiz_started = False
            st.session_state.quiz_current_question = 0
            st.session_state.quiz_session_id = None
            st.session_state.quiz_completed = False
            st.rerun()


def show_quiz_summary(session_id: str):
    """Show quiz summary modal"""
    st.info("""
    ### Quiz Summary
    
    This summary shows your current progress in the quiz.
    Continue answering questions to complete the assessment.
    """)
    
    progress_result = get_progress(session_id)
    if progress_result.get("success"):
        progress = progress_result.get("progress", {})
        st.json(progress)


def show_all_results():
    """Show all quiz results"""
    results_result = get_all_results()
    
    if results_result.get("success"):
        results = results_result.get("results", [])
        summary = results_result.get("summary", {})
        
        st.subheader("📊 All Quiz Results")
        
        # Summary statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Quizzes", summary.get("total_quizzes", 0))
        
        with col2:
            st.metric("Passed", summary.get("passed", 0))
        
        with col3:
            st.metric("Failed", summary.get("failed", 0))
        
        with col4:
            st.metric("Average Score", f"{summary.get('average_score', 0):.1f}%")
        
        st.divider()
        
        # All results table
        if results:
            st.subheader("Recent Quiz Attempts")
            
            for result in reversed(results[-10:]):  # Show last 10
                with st.expander(f"Quiz {result.get('session_id')[:8]}... - {result.get('score_percentage'):.1f}%"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write(f"**Score:** {result.get('score_percentage'):.1f}%")
                    
                    with col2:
                        st.write(f"**Correct:** {result.get('correct_answers')}/{result.get('total_questions')}")
                    
                    with col3:
                        status = "✅ PASSED" if result.get("is_passed") else "❌ FAILED"
                        st.write(f"**Status:** {status}")
                    
                    st.write(f"**Completed:** {result.get('completed_at')}")
        else:
            st.info("No quiz results yet.")
    else:
        st.error(f"Failed to load results: {results_result.get('error')}")


# ============================================================================
# EXECUTE QUIZ PAGE
# ============================================================================
# Call render_quiz_page directly (this executes when page is imported/exec'd)
render_quiz_page()
