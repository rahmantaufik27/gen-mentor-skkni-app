"""
Quiz Page Component for Streamlit

Route Protection:
- Requires authentication (redirects to login if not authenticated)
- Only accessible to authenticated users
- Displays personalized quiz assessment for learners
"""

import streamlit as st
from utils.quiz_api import (
    start_quiz, get_question, submit_answer,
    complete_quiz, get_quiz_history
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
    
    # Get current question
    question_result = get_question(session_id, question_index)
    if not question_result.get("success"):
        st.error("Failed to load question")
        return
    
    # Question data is at root level of response (not nested under "question" key)
    total_questions = question_result.get("total_questions", 36)
    question_number = question_result.get("question_number", question_index + 1)
    question_text = question_result.get("question_text", "")
    unit = question_result.get("unit", "")
    bloom_level = question_result.get("bloom_level", "")
    choices = question_result.get("choices", [])
    
    # Progress bar
    progress_percentage = question_number / total_questions
    st.progress(progress_percentage, text=f"Progress: {question_number}/{total_questions} questions")
    
    st.divider()
    
    # Display question
    st.subheader(f"Question {question_number} of {total_questions}")
    
    # Unit and Bloom info
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Unit:** {unit}")
    with col2:
        st.write(f"**Bloom Level:** {bloom_level}")
    
    st.divider()
    
    st.write(f"### {question_text}")
    
    # Answer options
    if not choices:
        st.warning("No answer choices available")
        return
    
    # Create choice text with letters
    choice_options = [f"{choice.get('id')}. {choice.get('text')}" for choice in choices]
    
    # Store selected answer
    selected_text = st.radio(
        label="Select your answer:",
        options=choice_options,
        key=f"question_{question_number}"
    )
    
    # Get choice ID from selection
    if selected_text:
        selected_choice_id = selected_text.split(".")[0]  # Extract letter (A, B, C, D)
        
        st.divider()
        
        col1, col2, col3 = st.columns(3)
        
        # Submit answer
        with col1:
            if st.button("Submit Answer", use_container_width=True, type="primary"):
                submit_result = submit_answer(
                    session_id,
                    question_index,
                    selected_choice_id
                )
                
                if submit_result.get("success"):
                    progress_data = submit_result.get("progress", {})
                    
                    # Check if quiz is completed
                    if progress_data.get("answered") >= total_questions:
                        # Quiz finished - auto-complete
                        complete_result = complete_quiz(session_id)
                        if complete_result.get("success"):
                            st.session_state.quiz_completed = True
                            st.session_state.quiz_result = complete_result
                            st.rerun()
                    else:
                        # Move to next question
                        st.session_state.quiz_current_question += 1
                        st.rerun()
                else:
                    st.error(f"Failed to submit answer: {submit_result.get('error')}")
        
        # View progress
        with col2:
            if st.button("View Progress", use_container_width=True):
                st.info(f"Answered: {question_number} / {total_questions}")
        
        # Quit quiz
        with col3:
            if st.button("Exit Quiz", use_container_width=True):
                st.session_state.quiz_started = False
                st.session_state.quiz_current_question = 0
                st.session_state.quiz_session_id = None
                st.rerun()


def render_quiz_results():
    """Render quiz results with mastery information"""
    result_data = st.session_state.quiz_result or {}
    
    # Display results header
    st.subheader("Quiz Complete!")
    st.divider()
    
    # Main score display
    col1, col2, col3, col4 = st.columns(4)
    
    total_questions = result_data.get("total_questions", 0)
    correct_answers = result_data.get("correct_answers", 0)
    max_score = result_data.get("max_possible_score", 1)
    total_score = result_data.get("total_score", 0)
    
    with col1:
        score_percentage = (total_score / max_score * 100) if max_score > 0 else 0
        st.metric(
            "Score",
            f"{score_percentage:.1f}%",
            delta=f"{correct_answers}/{total_questions}"
        )
    
    with col2:
        status = "PASSED" if result_data.get("is_passed") else "FAILED"
        st.metric("Status", status)
    
    with col3:
        st.metric("Total Points", f"{total_score}")
    
    with col4:
        st.metric("Max Possible", f"{max_score}")
    
    st.divider()
    
    # Pass/Fail determination
    is_passed = result_data.get("is_passed", False)
    
    if is_passed:
        st.success(f"Congratulations! You passed the quiz!")
    else:
        st.warning(f"You did not pass this time. Keep practicing!")
    
    st.divider()
    
    # Unit Mastery Summary
    st.subheader("Unit Mastery Summary")
    
    unit_mastery = result_data.get("unit_mastery", {})
    mastered_units = result_data.get("mastered_units", [])
    remedial_units = result_data.get("remedial_units", [])
    
    if unit_mastery:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Mastered Units")
            if mastered_units:
                for unit in mastered_units:
                    unit_data = unit_mastery.get(unit, {})
                    score = unit_data.get("score", 0)
                    max_s = unit_data.get("max", 21)
                    st.success(f"{unit}: {score}/{max_s} points")
            else:
                st.info("No units mastered yet")
        
        with col2:
            st.markdown("### Remedial Units (Need Improvement)")
            if remedial_units:
                for unit in remedial_units:
                    unit_data = unit_mastery.get(unit, {})
                    score = unit_data.get("score", 0)
                    max_s = unit_data.get("max", 21)
                    st.warning(f"{unit}: {score}/{max_s} points")
            else:
                st.info("All units mastered!")
    
    st.divider()
    
    # Action buttons
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Take Another Quiz", use_container_width=True, type="primary"):
            st.session_state.quiz_started = False
            st.session_state.quiz_current_question = 0
            st.session_state.quiz_session_id = None
            st.session_state.quiz_completed = False
            st.session_state.quiz_result = None
            st.rerun()
    
    with col2:
        if st.button("View Quiz History", use_container_width=True):
            show_quiz_history()
    
    with col3:
        if st.button("Go Home", use_container_width=True):
            st.session_state.quiz_started = False
            st.session_state.quiz_current_question = 0
            st.session_state.quiz_session_id = None
            st.session_state.quiz_completed = False
            st.session_state.quiz_result = None
            st.rerun()


def show_quiz_history():
    """Show user's quiz history"""
    history_result = get_quiz_history(limit=10)
    
    if history_result.get("success"):
        attempts = history_result.get("attempts", [])
        
        st.subheader("Your Quiz History")
        
        if attempts:
            for idx, attempt in enumerate(attempts, 1):
                with st.expander(f"Attempt {idx} - {attempt.get('status')}"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write(f"**Score:** {attempt.get('total_score')} points")
                    
                    with col2:
                        st.write(f"**Correct:** {attempt.get('correct_answers')}/{attempt.get('total_questions')}")
                    
                    with col3:
                        status = attempt.get('status', 'UNKNOWN')
                        st.write(f"**Status:** {status}")
                    
                    st.write(f"**Date:** {attempt.get('completed_at')}")
        else:
            st.info("No quiz attempts yet")
    else:
        st.error(f"Failed to load history: {history_result.get('error')}")


def show_all_results():
    """Show all results summary"""
    history_result = get_quiz_history(limit=100)
    
    if history_result.get("success"):
        attempts = history_result.get("attempts", [])
        
        st.subheader("All Quiz Results")
        
        if attempts:
            # Summary stats
            total_attempts = len(attempts)
            passed = sum(1 for a in attempts if a.get('status') == 'PASS')
            failed = total_attempts - passed
            avg_score = sum(a.get('total_score', 0) for a in attempts) / total_attempts if total_attempts > 0 else 0
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Attempts", total_attempts)
            
            with col2:
                st.metric("Passed", passed)
            
            with col3:
                st.metric("Failed", failed)
            
            with col4:
                st.metric("Avg Score", f"{avg_score:.1f}")
            
            st.divider()
            
            # Show recent attempts
            st.subheader("Recent Attempts")
            show_quiz_history()
        else:
            st.info("No quiz attempts yet")
    else:
        st.error(f"Failed to load results: {history_result.get('error')}")


# ============================================================================
# EXECUTE QUIZ PAGE
# ============================================================================
# Call render_quiz_page directly (this executes when page is imported/exec'd)
render_quiz_page()
