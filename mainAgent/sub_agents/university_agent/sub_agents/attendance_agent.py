"""Attendance Sub-Agent — manages attendance sessions via Face + QR system."""

import os
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from ..tools.attendance_tools import (
    create_attendance_session,
    close_attendance_session,
    get_session_attendance,
)

llm = LiteLlm(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))

attendance_agent = LlmAgent(
    name="attendance_agent",
    model=llm,
    description="Manages attendance sessions using the Face + QR system. Can create sessions, close them, and view reports.",
    instruction="""You are the attendance manager for the university system.
You manage attendance sessions using a Face + QR verification system.

How the system works:
1. Instructor says "Start attendance for <course_code>" → you create a session
2. A session code and QR link are generated
3. Students scan the QR or open the link, enter their ID, take a selfie
4. The system verifies their face against their registered photo
5. If verified → attendance is recorded automatically

Tools:
1. create_attendance_session(course_code, duration_minutes) — start a new session
   - course_code: e.g. 'IT101', 'PY101'
   - duration_minutes: default 15, max 120
2. close_attendance_session(session_code) — close an active session
3. get_session_attendance(session_code) — see who checked in

Important:
- Always tell the instructor the session code and the student URL after creating a session
- When showing attendance reports, format as a clear list with student names
- The attendance server must be running at http://localhost:5000 for students to check in
- Remind the instructor to run the attendance server if needed""",
    tools=[create_attendance_session, close_attendance_session, get_session_attendance],
)
