"""
tools.py - Academic Analyzer Secure Tools

Four secure tools for the academic_analyzer agent:
  1. get_student_attendance_summary  — Overall attendance % per course + warnings
  2. get_course_session_log          — Detailed per-lecture log (present/absent)
  3. get_missed_lectures             — List of lectures the student missed
  4. get_missed_lecture_summaries    — Summaries/key-points of missed lectures

Security:
  - Every tool receives `student_code` injected by the server.
  - No raw SQL is exposed to the LLM; all queries are parameterized.
  - Tools refuse empty/invalid student codes immediately.
"""

from mainAgent.db.database import get_connection, release_connection
import traceback


# ═══════════════════════════════════════════════════════════════════════
# INTERNAL HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _validate_student_code(student_code: str) -> dict | None:
    """Return an error dict if the code is missing/invalid, else None."""
    if not student_code or not str(student_code).strip():
        return {"status": "error", "message": "⚠️ مفيش كود طالب متاح. تأكد إنك مسجّل دخول."}
    return None


def _resolve_student(cur, student_code: str) -> tuple | None:
    """Resolve (student_id, student_name) from student_code. Returns None if not found."""
    cur.execute("SELECT id, name FROM profiles WHERE student_code = %s", (str(student_code).strip(),))
    return cur.fetchone()


def _resolve_course(cur, course_code_or_name: str):
    """Resolve course row from a code or name substring. Returns None if not found."""
    pattern = f"%{course_code_or_name}%"
    cur.execute(
        "SELECT id, name, course_code FROM courses WHERE course_code ILIKE %s OR name ILIKE %s LIMIT 1",
        (pattern, pattern),
    )
    return cur.fetchone()


# ═══════════════════════════════════════════════════════════════════════
# TOOL 1: ATTENDANCE SUMMARY
# ═══════════════════════════════════════════════════════════════════════

def get_student_attendance_summary(student_code: str) -> dict:
    """Retrieve a summary of the student's attendance in all courses.

    Shows attendance rate, absent count, and warning status per course.
    A warning fires when attendance drops below 75%.

    Args:
        student_code: The student's academic code (e.g. '20220101').

    Returns:
        A dict with 'status' ('success' or 'error') and 'data' containing attendance details.
    """
    err = _validate_student_code(student_code)
    if err:
        return err

    conn = get_connection()
    try:
        cur = conn.cursor()

        # 1. Resolve student
        student = _resolve_student(cur, student_code)
        if not student:
            return {"status": "error", "message": f"مفيش طالب بالكود ده: {student_code}"}

        student_id = student["id"]
        student_name = student["name"]

        # 2. Get attendance rates per course
        cur.execute("""
            SELECT 
                c.id AS course_id,
                c.course_code,
                c.name AS course_name,
                COALESCE(s_count.total, 0) AS total_sessions,
                COALESCE(a_count.attended, 0) AS attended_sessions
            FROM courses c
            LEFT JOIN (
                SELECT course_id, COUNT(*) AS total 
                FROM attendance_sessions 
                GROUP BY course_id
            ) s_count ON s_count.course_id = c.id
            LEFT JOIN (
                SELECT s.course_id, COUNT(a.id) AS attended
                FROM attendance a
                JOIN attendance_sessions s ON a.session_id = s.session_id
                WHERE a.student_id = %s
                GROUP BY s.course_id
            ) a_count ON a_count.course_id = c.id
            ORDER BY c.course_code
        """, (student_id,))

        rows = cur.fetchall()
        courses_data = []

        for r in rows:
            total = int(r["total_sessions"])
            attended = int(r["attended_sessions"])
            absent = max(0, total - attended)
            rate = (attended / total * 100) if total > 0 else 100.0

            # Warning logic: university typical warning threshold is < 75%
            warning_active = (rate < 75.0) and (total > 0)

            # Calculate remaining allowed absences before deprivation
            max_allowed_absent = int(total * 0.25)  # 25% of total
            remaining_absences = max(0, max_allowed_absent - absent)

            courses_data.append({
                "course_code": r["course_code"],
                "course_name": r["course_name"],
                "total_lectures": total,
                "attended": attended,
                "absent": absent,
                "attendance_rate": f"{rate:.1f}%",
                "warning": warning_active,
                "remaining_absences_before_deprivation": remaining_absences,
            })

        return {
            "status": "success",
            "student_name": student_name,
            "student_code": student_code,
            "courses": courses_data,
        }

    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        release_connection(conn)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 2: COURSE SESSION LOG
# ═══════════════════════════════════════════════════════════════════════

def get_course_session_log(student_code: str, course_code_or_name: str) -> dict:
    """Get the detailed log of every lecture/session for a specific course,
    showing whether the student was Present or Absent.

    Args:
        student_code: The student's academic code (e.g. '20220101').
        course_code_or_name: The course code (e.g. 'CS101') or name (e.g. 'C++').

    Returns:
        A dict with 'status' and the log of lectures.
    """
    err = _validate_student_code(student_code)
    if err:
        return err
    if not course_code_or_name:
        return {"status": "error", "message": "لازم تحدد المادة."}

    conn = get_connection()
    try:
        cur = conn.cursor()

        # 1. Resolve student
        student = _resolve_student(cur, student_code)
        if not student:
            return {"status": "error", "message": "مفيش طالب بالكود ده."}
        student_id = student["id"]

        # 2. Resolve course
        course = _resolve_course(cur, course_code_or_name)
        if not course:
            return {"status": "error", "message": f"مفيش مادة اسمها أو كودها '{course_code_or_name}'."}
        course_id = course["id"]

        # 3. Fetch all sessions + attendance
        cur.execute("""
            SELECT 
                s.session_id,
                s.session_code,
                s.created_at,
                a.id AS attendance_id,
                a.created_at AS attended_at
            FROM attendance_sessions s
            LEFT JOIN attendance a ON a.session_id = s.session_id AND a.student_id = %s
            WHERE s.course_id = %s
            ORDER BY s.created_at ASC
        """, (student_id, course_id))

        rows = cur.fetchall()
        sessions = []
        for idx, r in enumerate(rows, start=1):
            attended = r["attendance_id"] is not None
            sessions.append({
                "lecture_number": idx,
                "session_code": r["session_code"],
                "date": str(r["created_at"]),
                "status": "✅ Present" if attended else "❌ Absent",
                "attended_at": str(r["attended_at"]) if r["attended_at"] else None,
            })

        return {
            "status": "success",
            "course_name": course["name"],
            "course_code": course["course_code"],
            "sessions": sessions,
        }

    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        release_connection(conn)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 3: MISSED LECTURES
# ═══════════════════════════════════════════════════════════════════════

def get_missed_lectures(student_code: str, course_code_or_name: str = "") -> dict:
    """Get the list of lectures a student missed (was absent from).

    If course_code_or_name is provided, only shows missed lectures for that course.
    If empty, shows missed lectures across ALL courses.

    Args:
        student_code: The student's academic code (e.g. '20220101').
        course_code_or_name: Optional — course code or name to filter by.

    Returns:
        A dict with missed lectures grouped by course.
    """
    err = _validate_student_code(student_code)
    if err:
        return err

    conn = get_connection()
    try:
        cur = conn.cursor()

        # 1. Resolve student
        student = _resolve_student(cur, student_code)
        if not student:
            return {"status": "error", "message": "مفيش طالب بالكود ده."}
        student_id = student["id"]

        # 2. Build course filter
        course_filter = ""
        params = [student_id]

        if course_code_or_name:
            course = _resolve_course(cur, course_code_or_name)
            if not course:
                return {"status": "error", "message": f"مفيش مادة اسمها أو كودها '{course_code_or_name}'."}
            course_filter = "AND s.course_id = %s"
            params.append(course["id"])

        # 3. Find sessions where the student has NO attendance record
        cur.execute(f"""
            SELECT 
                c.course_code,
                c.name AS course_name,
                s.session_id,
                s.created_at AS session_date
            FROM attendance_sessions s
            JOIN courses c ON c.id = s.course_id
            LEFT JOIN attendance a ON a.session_id = s.session_id AND a.student_id = %s
            WHERE a.id IS NULL
            {course_filter}
            ORDER BY c.course_code, s.created_at ASC
        """, params)

        rows = cur.fetchall()

        # Group by course
        missed_by_course = {}
        for r in rows:
            key = r["course_code"]
            if key not in missed_by_course:
                missed_by_course[key] = {
                    "course_code": r["course_code"],
                    "course_name": r["course_name"],
                    "missed_lectures": [],
                }
            missed_by_course[key]["missed_lectures"].append({
                "date": str(r["session_date"]),
            })

        return {
            "status": "success",
            "student_name": student["name"],
            "total_missed": len(rows),
            "courses": list(missed_by_course.values()),
        }

    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
    finally:
        release_connection(conn)


# ═══════════════════════════════════════════════════════════════════════
# TOOL 4: MISSED LECTURE SUMMARIES
# ═══════════════════════════════════════════════════════════════════════

def get_missed_lecture_summaries(student_code: str, course_code_or_name: str = "") -> dict:
    """Get summaries and key points of lectures the student missed.
    Since lecture materials are now stored elsewhere, this tool will just instruct the agent to refer the user to the study agent.
    """
    return {
        "status": "success",
        "message": "لا يوجد ملخصات هنا لأن الماتيريال أصبحت في قاعدة البيانات الخاصة بـ study agent. يرجى إخبار الطالب بأن يسأل الـ study agent عن ملخص المادة."
    }
