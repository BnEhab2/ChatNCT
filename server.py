import os
import sys
import asyncio
import json
import traceback
import threading
import warnings
import requests as http_requests
from datetime import datetime
from dotenv import load_dotenv

# Suppress urllib3 SSL warnings (we use self-signed certs for local dev)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "mainAgent", ".env"))

# ── Google ADK imports ─────────────────────────────────────────────────
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from mainAgent.agent import root_agent

# ── Database imports ───────────────────────────────────────────────────
from mainAgent.db.database import (
    get_connection, release_connection, run_migrations
)

# ── Flask App ──────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="frontend", static_url_path="")
CORS(app)

# Disable caching for static files during development
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.after_request
def add_no_cache_headers(response):
    """Prevent browsers from caching JS/HTML files during development."""
    if response.content_type and ('javascript' in response.content_type or 'html' in response.content_type):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# Suppress verbose request logs (GET /img/Logo.png, etc.)
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# ── Run Migrations on Startup ─────────────────────────────────────────
try:
    run_migrations()
except Exception as e:
    print(f"Migration error (non-fatal): {e}")

# ── ADK Session Management ────────────────────────────────────────────
APP_NAME = "chatnct"
session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
)

# Store user sessions (user_id → session_id)
user_sessions = {}

ATTENDANCE_SERVER = os.getenv("ATTENDANCE_SERVER_URL", "https://127.0.0.1:5001")

# ── Persistent Event Loop (Feature 9: Performance) ────────────────────
_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_loop_thread.start()


def run_async(coro):
    """Run an async coroutine on the persistent event loop."""
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    return future.result(timeout=120)


# ── Helper: Run agent ──────────────────────────────────────────────────
async def _run_agent(user_id: str, message: str) -> str:
    """Send a message to the root agent and collect the response."""
    if user_id not in user_sessions:
        session_result = session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
        )
        import inspect
        if inspect.iscoroutine(session_result):
            session = await session_result
        else:
            session = session_result
        user_sessions[user_id] = session.id

    session_id = user_sessions[user_id]

    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message)],
    )

    response_parts = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_parts.append(part.text)

    return "\n".join(response_parts) if response_parts else "عذراً، مفيش رد متاح دلوقتي."


# ══════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════

def _resolve_student_uuid(user_id: str) -> str:
    """Look up a student's UUID from their student_code in the profiles table. Returns None if not found."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM profiles WHERE student_code = %s", (user_id,))
        row = cur.fetchone()
        if row:
            return str(row["id"])
        return None
    finally:
        release_connection(conn)


# ══════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

# ── Chat (with Supabase persistence — Feature 1) ──────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    """Send a message to the root agent and return the response. Saves to DB."""
    data = request.get_json()
    message = data.get("message", "").strip()
    user_id = data.get("user_id", "default_user")
    chat_session_id = data.get("session_id", None)  # Supabase chat_sessions.id

    if not message:
        return jsonify({"status": "error", "code": "MISSING_MESSAGE", "message": "Message is required."}), 400

    try:
        # Create chat session if not provided
        if not chat_session_id:
            conn = get_connection()
            try:
                cur = conn.cursor()
                title = message[:50] + ("..." if len(message) > 50 else "")
                cur.execute(
                    "INSERT INTO chat_sessions (student_id, title) VALUES (%s, %s) RETURNING id",
                    (user_id, title)
                )
                chat_session_id = str(cur.fetchone()[0])
                conn.commit()
            finally:
                release_connection(conn)

        # Save user message
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO chat_messages (session_id, role, content) VALUES (%s, 'user', %s)",
                (chat_session_id, message)
            )
            conn.commit()
        finally:
            release_connection(conn)

        # Get agent response
        response = run_async(_run_agent(user_id, message))

        # Save bot response
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO chat_messages (session_id, role, content) VALUES (%s, 'bot', %s)",
                (chat_session_id, response)
            )
            conn.commit()
        finally:
            release_connection(conn)

        return jsonify({
            "status": "success",
            "response": response,
            "session_id": chat_session_id,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "code": "AGENT_ERROR",
            "message": f"Agent error: {str(e)}",
            "traceback": traceback.format_exc()
        }), 500


# ── Feature 1: Chat Sessions CRUD ─────────────────────────────────────
@app.route("/api/chat/sessions", methods=["GET"])
def list_chat_sessions():
    """List chat sessions for a user with pagination."""
    user_id = request.args.get("user_id", "default_user")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 20))
    offset = (page - 1) * per_page

    conn = get_connection()
    try:
        cur = conn.cursor()
        # Get total count
        cur.execute("SELECT COUNT(*) FROM chat_sessions WHERE student_id = %s", (user_id,))
        total = cur.fetchone()[0]

        # Get sessions
        cur.execute("""
            SELECT id, title, created_at FROM chat_sessions
            WHERE student_id = %s ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """, (user_id, per_page, offset))
        sessions = []
        for row in cur.fetchall():
            r = dict(row)
            r["id"] = str(r["id"])
            r["created_at"] = str(r["created_at"])
            sessions.append(r)

        return jsonify({
            "status": "success",
            "sessions": sessions,
            "total": total,
            "page": page,
            "per_page": per_page,
        })
    finally:
        release_connection(conn)


@app.route("/api/chat/sessions/<session_id>/messages", methods=["GET"])
def get_chat_messages(session_id):
    """Get messages for a chat session with pagination."""
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 50))
    offset = (page - 1) * per_page

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM chat_messages WHERE session_id = %s", (session_id,))
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT id, role, content, created_at FROM chat_messages
            WHERE session_id = %s ORDER BY created_at ASC
            LIMIT %s OFFSET %s
        """, (session_id, per_page, offset))
        messages = []
        for row in cur.fetchall():
            r = dict(row)
            r["id"] = str(r["id"])
            r["created_at"] = str(r["created_at"])
            messages.append(r)

        return jsonify({
            "status": "success",
            "messages": messages,
            "total": total,
            "page": page,
            "per_page": per_page,
        })
    finally:
        release_connection(conn)


@app.route("/api/chat/sessions/<session_id>", methods=["DELETE"])
def delete_chat_session(session_id):
    """Delete a chat session and all its messages."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM chat_sessions WHERE id = %s", (session_id,))
        affected = cur.rowcount
        conn.commit()
        if affected == 0:
            return jsonify({"status": "error", "code": "SESSION_NOT_FOUND", "message": "Session not found."}), 404
        return jsonify({"status": "success", "message": "Session deleted."})
    finally:
        release_connection(conn)


@app.route("/api/chat/sessions/<session_id>/rename", methods=["PUT"])
def rename_chat_session(session_id):
    """Rename a chat session."""
    data = request.get_json()
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"status": "error", "code": "MISSING_TITLE", "message": "Title is required."}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE chat_sessions SET title = %s WHERE id = %s", (title, session_id))
        affected = cur.rowcount
        conn.commit()
        if affected == 0:
            return jsonify({"status": "error", "code": "SESSION_NOT_FOUND", "message": "Session not found."}), 404
        return jsonify({"status": "success", "message": "Session renamed."})
    finally:
        release_connection(conn)


# ── Prompt Generation ─────────────────────────────────────────────────
@app.route("/api/prompt/generate", methods=["POST"])
def generate_prompt():
    data = request.get_json()
    idea = data.get("idea", "").strip()
    user_id = data.get("user_id", "prompt_user")

    if not idea:
        return jsonify({"status": "error", "message": "Idea is required."}), 400

    try:
        prompt_message = f"اعملي prompt احترافي للفكرة دي: {idea}"
        response = run_async(_run_agent(user_id, prompt_message))
        return jsonify({"status": "success", "prompt": response})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Agent error: {str(e)}"}), 500


# ── Code Generation (Vibe Coder) ──────────────────────────────────────
@app.route("/api/code/generate", methods=["POST"])
def generate_code():
    data = request.get_json()
    prompt = data.get("prompt", "").strip()
    user_id = data.get("user_id", "code_user")

    if not prompt:
        return jsonify({"status": "error", "message": "Prompt is required."}), 400

    try:
        code_message = f"اكتبلي كود: {prompt}"
        response = run_async(_run_agent(user_id, code_message))
        return jsonify({"status": "success", "code": response})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Agent error: {str(e)}"}), 500


# ── Auth (Supabase Auth — server-side validation) ─────────────────────
@app.route("/api/auth/login", methods=["POST"])
def login():
    """Validate user credentials via Supabase Auth and return profile info."""
    data = request.get_json()
    email = data.get("email", "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password required."}), 400

    # Authenticate via Supabase Auth
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")

    try:
        auth_res = http_requests.post(
            f"{supabase_url}/auth/v1/token?grant_type=password",
            headers={
                "apikey": supabase_key,
                "Content-Type": "application/json",
            },
            json={"email": email, "password": password},
            timeout=10,
        )
        auth_data = auth_res.json()

        if auth_res.status_code != 200:
            error_msg = auth_data.get("error_description") or auth_data.get("msg") or "Invalid credentials."
            return jsonify({"status": "error", "message": error_msg}), 401

        access_token = auth_data.get("access_token", "")
        refresh_token = auth_data.get("refresh_token", "")
        user_id = auth_data.get("user", {}).get("id", "")
    except Exception as e:
        return jsonify({"status": "error", "message": f"Auth service error: {str(e)}"}), 500

    # Fetch profile from unified profiles table
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, role, status, student_code FROM profiles WHERE id = %s",
            (user_id,)
        )
        row = cur.fetchone()

        if not row:
            return jsonify({"status": "error", "message": "Profile not found."}), 404

        profile = dict(row)
        role = profile["role"]
        display_name = profile["name"]
        student_code = profile.get("student_code", "")
    finally:
        release_connection(conn)

    return jsonify({
        "status": "success",
        "is_admin": role in ("instructor", "admin"),
        "username": display_name,
        "role": role,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user_id": student_code or str(user_id),
    })


# ══════════════════════════════════════════════════════════════════════
# ATTENDANCE SERVER PROXY
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/courses", methods=["GET"])
def get_courses():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT c.id AS course_id, c.course_code, c.name AS course_name,
                   c.instructor_id, p.name AS instructor_name
            FROM courses c
            LEFT JOIN profiles p ON c.instructor_id = p.id
            ORDER BY c.course_code
        """)
        rows = [dict(r) for r in cur.fetchall()]
        return jsonify(rows)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        release_connection(conn)


@app.route("/api/session/create", methods=["POST"])
def proxy_create_session():
    try:
        r = http_requests.post(
            f"{ATTENDANCE_SERVER}/api/session/create",
            json=request.get_json(),
            verify=False, timeout=15,
        )
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/session/<code>", methods=["GET"])
def proxy_check_session(code):
    try:
        r = http_requests.get(f"{ATTENDANCE_SERVER}/api/session/{code}", verify=False, timeout=15)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/session/<code>/qr-token", methods=["GET"])
def proxy_qr_token(code):
    """Proxy: get rotating QR token."""
    try:
        r = http_requests.get(f"{ATTENDANCE_SERVER}/api/session/{code}/qr-token", verify=False, timeout=15)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/attendance/verify", methods=["POST"])
def proxy_verify_attendance():
    try:
        r = http_requests.post(
            f"{ATTENDANCE_SERVER}/api/attendance/verify",
            json=request.get_json(),
            verify=False, timeout=120,
        )
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/attendance/check_identity", methods=["POST"])
def proxy_check_identity():
    try:
        r = http_requests.post(
            f"{ATTENDANCE_SERVER}/api/attendance/check_identity",
            json=request.get_json(),
            verify=False, timeout=120,
        )
        resp_data = r.json()
        sys.stderr.write(f"[FACE-DEBUG] verified={resp_data.get('verified')}, "
              f"distance={resp_data.get('distance')}, msg={resp_data.get('message')}, "
              f"faceBox={resp_data.get('faceBox')}\n")
        sys.stderr.flush()
        return jsonify(resp_data), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server unreachable: {e}"}), 502


@app.route("/api/attendance/check_pose", methods=["POST"])
def proxy_check_pose():
    try:
        r = http_requests.post(
            f"{ATTENDANCE_SERVER}/api/attendance/check_pose",
            json=request.get_json(),
            verify=False, timeout=10,
        )
        resp_data = r.json()
        sys.stderr.write(f"[POSE-DEBUG] pose={resp_data.get('pose')}\n")
        sys.stderr.flush()
        return jsonify(resp_data), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server unreachable: {e}"}), 502


@app.route("/api/attendance/challenges", methods=["GET"])
def proxy_challenges():
    """Proxy: get liveness challenges."""
    try:
        r = http_requests.get(f"{ATTENDANCE_SERVER}/api/attendance/challenges", verify=False, timeout=15)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/attendance/prepare", methods=["POST"])
def proxy_prepare():
    """Proxy: pre-cache student embedding for fast identity check."""
    try:
        r = http_requests.post(
            f"{ATTENDANCE_SERVER}/api/attendance/prepare",
            json=request.get_json(),
            verify=False, timeout=30,
        )
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/session/<code>/report", methods=["GET"])
def proxy_session_report(code):
    try:
        r = http_requests.get(f"{ATTENDANCE_SERVER}/api/session/{code}/report", verify=False, timeout=15)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/session/<code>/close", methods=["POST"])
def proxy_close_session(code):
    try:
        r = http_requests.post(f"{ATTENDANCE_SERVER}/api/session/{code}/close", verify=False, timeout=15)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


# ══════════════════════════════════════════════════════════════════════
# FRONTEND SERVING
# ══════════════════════════════════════════════════════════════════════

@app.route("/")
def serve_index():
    return send_from_directory("frontend", "index.html")


@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("frontend", path)


# ══════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import ssl
    import socket

    def get_lan_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    try:
        from mainAgent.web.generate_cert import generate_self_signed_cert
        cert_dir = os.path.dirname(__file__)
        cert_path, key_path = generate_self_signed_cert(cert_dir)
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(cert_path, key_path)
    except Exception as e:
        print(f"Warning: Could not generate SSL certs. Falling back to HTTP. {e}")
        ssl_ctx = None

    lan_ip = get_lan_ip()
    protocol = "https" if ssl_ctx else "http"

    # print("\n" + "=" * 60)
    # print(" ChatNCT Server (Unified App)")
    # print("=" * 60)
    # print(f"  Local:      {protocol}://localhost:5000/")
    # print(f"  Network:    {protocol}://{lan_ip}:5000/")
    # print("=" * 60)
    # print("[WARNING]  To test from mobile camera, you MUST open the Network link")
    # print("   on your mobile and accept the 'Not Secure' warning.")
    # print("=" * 60 + "\n")

    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False, ssl_context=ssl_ctx)