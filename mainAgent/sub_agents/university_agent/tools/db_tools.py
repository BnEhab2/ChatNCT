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

    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
    tables = [row[0] for row in cur.fetchall()]

    schema = {}
    for table in tables:
        cur.execute("""
            SELECT column_name, data_type, is_nullable, 
                   (SELECT COUNT(*) FROM information_schema.key_column_usage kcu JOIN information_schema.table_constraints tc ON kcu.constraint_name = tc.constraint_name WHERE kcu.table_name = c.table_name AND kcu.column_name = c.column_name AND tc.constraint_type = 'PRIMARY KEY') as is_pk
            FROM information_schema.columns c
            WHERE table_schema = 'public' AND table_name = %s
        """, (table,))
        columns = [{"name": col[0], "type": col[1], "nullable": col[2] == 'YES', "pk": col[3] > 0} for col in cur.fetchall()]
        schema[table] = columns

    conn.close()
    return {"status": "success", "schema": schema}
