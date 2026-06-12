import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mainAgent.db.database import get_connection, release_connection

conn = get_connection()
try:
    cur = conn.cursor()
    # Find student_id for the session
    cur.execute("SELECT student_id FROM chat_sessions WHERE id = %s", ('9f069dd3-3637-4559-a933-2ca1619e2d3c',))
    row = cur.fetchone()
    if row:
        student_id = row['student_id']
        print(f"Student ID: {student_id}")
        
        # Get profile info
        cur.execute("SELECT * FROM profiles WHERE id::text = %s OR student_code = %s", (student_id, student_id))
        profile = cur.fetchone()
        if profile:
            print("Profile Info:")
            for k, v in dict(profile).items():
                print(f"  {k}: {v}")
        else:
            print("Profile not found in DB!")
    else:
        print("Session not found!")
finally:
    release_connection(conn)
