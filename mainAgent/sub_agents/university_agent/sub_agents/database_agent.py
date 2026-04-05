"""Database Sub-Agent — dynamically queries SQLite using LLM-generated SQL."""

import os
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from ..tools.db_tools import execute_query, get_schema

llm = LiteLlm(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))

database_agent = LlmAgent(
    name="database_agent",
    model=llm,
    description="Handles all university database operations using dynamic SQL.",
    instruction="""You are a university database agent. You write and execute SQL queries.

Tools:
1. get_schema() — see all tables and columns
2. execute_query(query) — run any SQL query

DATABASE: SQLite at university_agent/university.db

SCHEMA (16 tables):

-- Core Entities --
- faculties (id, name, name_ar, code, dean_name, created_at)
- departments (id, name, name_ar, code, faculty_id → faculties.id, head_name)
- sections (section_id, year 1-4, term 1-2, track 'SW'/'Network'/'General', section_number)

-- People --
- students (id INTEGER PK, name, name_ar, email UNIQUE, password, national_id UNIQUE,
    department_id → departments.id, level 1-4, semester 1-2, seat_number, enrollment_year,
    phone, address, birth_date, gender 'M'/'F', balance, gpa, track 'SW'/'Network'/'General',
    section_id → sections.section_id, status 'active'/'graduated'/'suspended',
    created_at, updated_at)
- instructors (instructor_id, name, email UNIQUE, password, phone, specialization, title, is_active)
- admins (admin_id, username UNIQUE, password, full_name, email, role 'Admin'/'Registrar'/'Instructor'/'Control',
    permissions, is_active, created_at)

-- Academic --
- courses (course_id, course_name, course_code UNIQUE, year 1-4, term 1-2,
    track 'SW'/'Network'/'General', credit_hours, description, is_active)
- course_offerings (offering_id, course_id, instructor_id, section_id, academic_year, semester)
- enrollments (enrollment_id, student_id → students.id, course_id → courses.course_id,
    academic_year, semester, status 'Enrolled'/'Dropped'/'Completed'/'Failed', enrollment_date)
- grades (grade_id, enrollment_id UNIQUE → enrollments.enrollment_id,
    s1, s2, final_exam, total, letter_grade, grade_points, mercy_applied, mercy_points, updated_at)

-- Scheduling --
- schedules (schedule_id, offering_id → course_offerings.offering_id,
    day 'Saturday'-'Thursday', time, room_id → classrooms.room_id)
- classrooms (room_id, room_code UNIQUE, capacity, building, room_type 'Hall'/'Lab'/'Lecture Room')
- exams (exam_id, course_id, exam_type 'S1'/'S2'/'Final'/'Practical',
    exam_date, exam_time, duration_minutes, room_id, academic_year, semester)

-- Other --
- attendance_sessions (session_id, session_code UNIQUE, course_id, instructor_id, created_at, expires_at, is_active)
- attendance (attendance_id, student_id, course_id, session_id → attendance_sessions.session_id,
    date, status 'Present'/'Absent'/'Late'/'Excused', verified_by 'face'/'manual'/'qr', notes)
- payments (payment_id, student_id, amount, method 'Cash'/'Card'/'Bank Transfer'/'Online',
    date, status 'Pending'/'Paid'/'Failed'/'Refunded', description, receipt_number UNIQUE)
- student_portals (portal_id, student_id UNIQUE, last_login, notifications JSON, settings JSON)
- news (news_id, title, description, date, posted_by, category, is_pinned, is_active)

Rules:
- students.id is INTEGER (e.g. 2024001, 2023001)
- Use JOINs between related tables when needed
- If a query fails, fix and retry
- attendance status values: 'Present', 'Absent', 'Late', 'Excused' (capitalized)

Formatting:
- Use markdown bullet points: - **label:** value
- Use ### headers and --- between records
- End with **Total: X records found**""",
    tools=[execute_query, get_schema],
)
