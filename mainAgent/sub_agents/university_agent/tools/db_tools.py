"""Database tools — a single dynamic query tool for the agent."""

from ..db.database import get_connection


def execute_query(query: str) -> dict:
    """Execute a SQL query on the university database and return the results.

    Use this tool to run any SQL query (SELECT, INSERT, UPDATE, DELETE).
    The database has these tables: faculties, departments, sections, students,
    courses, instructors, classrooms, course_offerings, schedules, enrollments,
    grades, exams, attendance, payments, student_portals, news, admins.

    Args:
        query: A valid SQL query string to execute on the database.

    Returns:
        dict with status, row_count, and results (for SELECT) or a success message.
    """
    conn = get_connection()
    cur = conn.cursor()

    try:
        cur.execute(query)

        if query.strip().upper().startswith("SELECT"):
            columns = [desc[0] for desc in cur.description]
            rows = [dict(zip(columns, row)) for row in cur.fetchall()]
            conn.close()
            return {"status": "success", "row_count": len(rows), "results": rows}
        else:
            conn.commit()
            affected = cur.rowcount
            conn.close()
            return {"status": "success", "message": f"Query executed successfully. {affected} row(s) affected."}

    except Exception as e:
        conn.close()
        return {"status": "error", "error_message": str(e)}


def get_schema() -> dict:
    """Get the full database schema showing all tables and their columns.

    Returns:
        dict with status and the schema of all tables.
    """
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]

    schema = {}
    for table in tables:
        cur.execute(f"PRAGMA table_info({table})")
        columns = [{"name": col[1], "type": col[2], "nullable": not col[3], "pk": bool(col[5])} for col in cur.fetchall()]
        schema[table] = columns

    conn.close()
    return {"status": "success", "schema": schema}
