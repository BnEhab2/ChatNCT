"""Attendance tools — agent-callable functions for managing attendance sessions."""

import random
import string
from datetime import datetime, timedelta

from ..db.database import get_connection


def create_attendance_session(course_code: str, duration_minutes: int = 15) -> dict:
    """Create a new attendance session for a course.

    The instructor calls this to start an attendance session. A random 6-character
    code is generated. Students use this code (or scan the QR) to check in.

    Args:
        course_code: The course code, e.g. 'IT101'.
        duration_minutes: How long the session stays active (default 15 min).

    Returns:
        dict with session_code, student_url, and expiry time.
    """
    conn = get_connection()
    cur = conn.cursor()

    # Look up course
    cur.execute("SELECT course_id, course_name FROM courses WHERE course_code = ?", (course_code,))
    course = cur.fetchone()
    if not course:
        conn.close()
        return {"status": "error", "message": f"Course '{course_code}' not found."}

    course = dict(course)
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    now = datetime.now()
    expires = now + timedelta(minutes=duration_minutes)

    # Close any existing active sessions for this course
    cur.execute("UPDATE attendance_sessions SET is_active = 0 WHERE course_id = ? AND is_active = 1",
                (course["course_id"],))

    cur.execute("""
        INSERT INTO attendance_sessions (session_code, course_id, instructor_id, expires_at)
        VALUES (?, ?, 1, ?)
    """, (code, course["course_id"], expires.isoformat()))

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "session_code": code,
        "course": f"{course_code} — {course['course_name']}",
        "expires_at": expires.strftime("%H:%M:%S"),
        "duration_minutes": duration_minutes,
        "student_url": f"http://localhost:5000/student?code={code}",
        "message": (
            f"✅ Session created for {course_code}!\n"
            f"Session Code: **{code}**\n"
            f"Expires at: {expires.strftime('%H:%M:%S')}\n"
            f"Student link: http://localhost:5000/student?code={code}\n\n"
            f"Tell students to open the link or enter code **{code}** on the attendance page."
        ),
    }


def close_attendance_session(session_code: str) -> dict:
    """Close an active attendance session.

    Args:
        session_code: The 6-character session code to close.

    Returns:
        dict with status and message.
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE attendance_sessions SET is_active = 0 WHERE session_code = ? AND is_active = 1",
                (session_code,))
    affected = cur.rowcount
    conn.commit()
    conn.close()

    if affected == 0:
        return {"status": "error", "message": f"Session '{session_code}' not found or already closed."}

    return {"status": "success", "message": f"✅ Session **{session_code}** closed successfully."}


def get_session_attendance(session_code: str) -> dict:
    """Get the attendance report for a session.

    Args:
        session_code: The 6-character session code.

    Returns:
        dict with list of students who checked in.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM attendance_sessions WHERE session_code = ?", (session_code,))
    session = cur.fetchone()
    if not session:
        conn.close()
        return {"status": "error", "message": f"Session '{session_code}' not found."}

    session = dict(session)

    cur.execute("""
        SELECT a.student_id, s.name AS student_name, a.date, a.status, a.verified_by
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.session_id = ?
        ORDER BY a.attendance_id
    """, (session["session_id"],))

    records = [dict(r) for r in cur.fetchall()]
    conn.close()

    return {
        "status": "success",
        "session_code": session_code,
        "is_active": bool(session["is_active"]),
        "total_present": len(records),
        "students": records,
    }