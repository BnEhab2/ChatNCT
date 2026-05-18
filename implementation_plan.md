# Academic Analyzer - Implementation Plan

## Current State
- `academic_analyzer` agent exists with 2 tools: `get_student_attendance_summary` and `get_course_session_log`
- Database already has: `profiles`, `courses`, `attendance_sessions`, `attendance` tables
- Server already injects `[STUDENT_CODE: xxx]` into messages (line 129 in server.py)
- Agent already extracts student code from the prefix

## What Needs to Be Done

### 1. New Database Tables (Migrations)
- `lectures` — maps each attendance_session to a lecture with title/topic
- `lecture_summaries` — stores AI-generated summaries for each lecture

### 2. New Tools
- `get_missed_lectures` — returns list of lectures the student missed
- `get_lecture_summaries` — returns summaries for missed lectures

### 3. Security Hardening
- Add explicit student_code validation in every tool
- Block any user-supplied student codes (only use injected ones)
- Add guardrails in agent instructions

### 4. Enhanced Agent Instructions
- Egyptian dialect refinements
- Deprivation warnings (< 75% threshold)
- Cross-agent referrals (study_agent for summaries)

### 5. Updated Migrations in database.py
