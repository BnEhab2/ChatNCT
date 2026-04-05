import os
import sys
import socket
import random
import string
import base64
from datetime import datetime, timedelta

import cv2
import numpy as np
from flask import Flask, render_template, request, jsonify

# Add parent so we can import db module
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db.database import get_connection
try:
    from web.face_verifier import FaceVerifier
except ImportError:
    from face_verifier import FaceVerifier

# Initialize FaceVerifier once at startup
face_verifier = FaceVerifier()

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
    static_url_path="/static",
)

PACKAGE_DIR = os.path.dirname(os.path.dirname(__file__))
PHOTOS_DIR = os.path.join(PACKAGE_DIR, "photos")


def _get_lan_ip() -> str:
    
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


LAN_IP = _get_lan_ip()


# ── Helpers ────────────────────────────────────────────────────────────
def _generate_code(length: int = 6) -> str:
    """Generate a random alphanumeric session code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


def _decode_base64_image(data_url: str) -> np.ndarray:
    """Convert a base64 data URL to an OpenCV image."""
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    img_bytes = base64.b64decode(data_url)
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


# ── Pages ──────────────────────────────────────────────────────────────
@app.route("/")
def instructor_page():
    """Instructor dashboard."""
    return render_template("instructor.html")


@app.route("/student")
def student_page():
    """Student attendance verification page."""
    return render_template("student.html")


# ── API: Courses List ──────────────────────────────────────────────────
@app.route("/api/courses", methods=["GET"])
def list_courses():
    """Return active courses with their instructors."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.course_id, c.course_code, c.course_name,
               i.instructor_id, i.name AS instructor_name
        FROM courses c
        LEFT JOIN course_offerings co ON c.course_id = co.course_id
        LEFT JOIN instructors i ON co.instructor_id = i.instructor_id
        WHERE c.is_active = 1
        GROUP BY c.course_id
        ORDER BY c.course_code
    """)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(rows)


# ── API: Create Session ───────────────────────────────────────────────
@app.route("/api/session/create", methods=["POST"])
def create_session():
    """Instructor creates a new attendance session."""
    data = request.get_json()
    course_id = data.get("course_id")
    instructor_id = data.get("instructor_id", 1)
    duration = data.get("duration_minutes", 15)

    if not course_id:
        return jsonify({"status": "error", "message": "course_id is required."}), 400

    code = _generate_code()
    now = datetime.now()
    expires = now + timedelta(minutes=int(duration))

    conn = get_connection()
    cur = conn.cursor()

    # Close any active sessions for this course first
    cur.execute("""
        UPDATE attendance_sessions SET is_active = 0
        WHERE course_id = ? AND is_active = 1
    """, (course_id,))

    cur.execute("""
        INSERT INTO attendance_sessions (session_code, course_id, instructor_id, expires_at)
        VALUES (?, ?, ?, ?)
    """, (code, course_id, instructor_id, expires.isoformat()))

    session_id = cur.lastrowid
    conn.commit()

    # Get course info for response
    cur.execute("SELECT course_code, course_name FROM courses WHERE course_id = ?", (course_id,))
    course = dict(cur.fetchone())
    conn.close()

    return jsonify({
        "status": "success",
        "session_id": session_id,
        "session_code": code,
        "course": course,
        "expires_at": expires.isoformat(),
        "duration_minutes": duration,
    })


# ── API: Check Session ────────────────────────────────────────────────
@app.route("/api/session/<code>", methods=["GET"])
def check_session(code):
    """Check if a session code is valid and active."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.*, c.course_code, c.course_name, i.name AS instructor_name
        FROM attendance_sessions s
        JOIN courses c ON s.course_id = c.course_id
        JOIN instructors i ON s.instructor_id = i.instructor_id
        WHERE s.session_code = ?
    """, (code,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return jsonify({"status": "error", "message": "Session not found."}), 404

    session = dict(row)
    now = datetime.now()
    expires = datetime.fromisoformat(session["expires_at"])
    is_expired = now > expires

    if not session["is_active"] or is_expired:
        return jsonify({
            "status": "error",
            "message": "Session expired or closed.",
            "expired": is_expired,
        }), 410

    return jsonify({
        "status": "success",
        "session_id": session["session_id"],
        "course_code": session["course_code"],
        "course_name": session["course_name"],
        "instructor_name": session["instructor_name"],
        "expires_at": session["expires_at"],
    })


# ── API: Verify & Record Attendance ───────────────────────────────────
@app.route("/api/attendance/verify", methods=["POST"])
def verify_attendance():
    """Student submits selfie + session code → face verify → record attendance."""
    data = request.get_json()
    session_code = data.get("session_code", "").strip()
    student_id = data.get("student_id", "").strip()
    image_data = data.get("image", "")

    if not session_code or not student_id or not image_data:
        return jsonify({"status": "error", "message": "session_code, student_id and image are required."}), 400

    conn = get_connection()
    cur = conn.cursor()

    # 1) Validate session
    cur.execute("""
        SELECT * FROM attendance_sessions WHERE session_code = ? AND is_active = 1
    """, (session_code,))
    session = cur.fetchone()
    if not session:
        conn.close()
        return jsonify({"status": "error", "message": "Session not found or expired."}), 404

    session = dict(session)
    now = datetime.now()
    if now > datetime.fromisoformat(session["expires_at"]):
        conn.close()
        return jsonify({"status": "error", "message": "Session has expired."}), 410

    # 2) Get student photo
    cur.execute("SELECT id, name, photo_path FROM students WHERE id = ?", (student_id,))
    student = cur.fetchone()
    if not student:
        conn.close()
        return jsonify({"status": "error", "message": f"Student {student_id} not found."}), 404

    student = dict(student)
    photo_rel = student.get("photo_path")
    if not photo_rel:
        conn.close()
        return jsonify({"status": "error", "message": "No registered photo for this student. Please register a photo first."}), 400

    photo_path = os.path.join(PACKAGE_DIR, photo_rel) if not os.path.isabs(photo_rel) else photo_rel
    if not os.path.exists(photo_path):
        conn.close()
        return jsonify({"status": "error", "message": f"Photo file not found at {photo_path}."}), 400

    # 3) Check if already checked in
    cur.execute("""
        SELECT attendance_id FROM attendance
        WHERE student_id = ? AND session_id = ?
    """, (student_id, session["session_id"]))
    if cur.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "You already checked in for this session."}), 409

    # 4) Decode image & run face verification using FaceVerifier
    try:
        captured = _decode_base64_image(image_data)
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": f"Failed to decode image: {e}"}), 400

    try:
        verification = face_verifier.verifyIdentity(captured, photo_path)
        distance = round(verification["distance"], 4)
        verified = verification["verified"]
        print(f"Face verify: student={student_id}, distance={distance}, verified={verified}, message={verification['message']}")
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "message": f"Face verification error: {e}"}), 500

    if not verified:
        conn.close()
        return jsonify({
            "status": "error",
            "verified": False,
            "distance": distance,
            "message": f"Face verification failed. {verification['message']}",
        }), 403

    # 5) Record attendance
    today = now.strftime("%Y-%m-%d")
    cur.execute("""
        INSERT INTO attendance (student_id, course_id, session_id, date, status, verified_by, notes)
        VALUES (?, ?, ?, ?, 'Present', 'face', 'Verified via Face+QR')
    """, (student_id, session["course_id"], session["session_id"], today))
    conn.commit()
    conn.close()

    return jsonify({
        "status": "success",
        "verified": True,
        "distance": distance,
        "student_name": student["name"],
        "message": f"{student['name']} — Attendance recorded successfully!",
    })


# ── API: Session Report ───────────────────────────────────────────────
@app.route("/api/session/<code>/report", methods=["GET"])
def session_report(code):
    """Get attendance report for a session."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM attendance_sessions WHERE session_code = ?", (code,))
    session = cur.fetchone()
    if not session:
        conn.close()
        return jsonify({"status": "error", "message": "Session not found."}), 404

    session = dict(session)

    cur.execute("""
        SELECT a.attendance_id, a.student_id, s.name AS student_name,
               a.date, a.status, a.verified_by, a.notes
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        WHERE a.session_id = ?
        ORDER BY a.attendance_id
    """, (session["session_id"],))

    records = [dict(r) for r in cur.fetchall()]
    conn.close()

    return jsonify({
        "status": "success",
        "session_code": code,
        "total_present": len(records),
        "records": records,
    })


# ── API: Close Session ────────────────────────────────────────────────
@app.route("/api/session/<code>/close", methods=["POST"])
def close_session(code):
    """Close an active attendance session."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE attendance_sessions SET is_active = 0
        WHERE session_code = ? AND is_active = 1
    """, (code,))
    affected = cur.rowcount
    conn.commit()
    conn.close()

    if affected == 0:
        return jsonify({"status": "error", "message": "Session not found or already closed."}), 404

    return jsonify({"status": "success", "message": "Session closed."})


# ── Main ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import ssl
    import importlib
    # Handle both: python -m university_agent.web.attendance_server  AND  python attendance_server.py
    try:
        from university_agent.web.generate_cert import generate_self_signed_cert
    except ImportError:
        from generate_cert import generate_self_signed_cert

    cert_dir = os.path.dirname(__file__)
    cert_path, key_path = generate_self_signed_cert(cert_dir)

    print(f"\n📱 Face + QR Attendance Server (HTTPS)")
    print("=" * 55)
    print(f"  Local:      https://localhost:5000/")
    print(f"  Network:    https://{LAN_IP}:5000/")
    print(f"  Student:    https://{LAN_IP}:5000/student")
    print("=" * 55)
    print("⚠️  Mobile browsers will show a certificate warning —")
    print("   tap 'Advanced' → 'Proceed' to continue.\n")

    ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_ctx.load_cert_chain(cert_path, key_path)

    app.run(host="0.0.0.0", port=5000, debug=True, ssl_context=ssl_ctx, use_reloader=False)
