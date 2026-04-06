"""
server.py — ChatNCT Backend API Middleware

Central Flask server that connects the frontend with all AI agents.
Serves the frontend files and proxies requests to the appropriate agents
and the attendance server.
"""

import os
import sys
import asyncio
import json
import traceback
import requests as http_requests
from dotenv import load_dotenv

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

# Load environment variables from mainAgent/.env
load_dotenv(os.path.join(os.path.dirname(__file__), "mainAgent", ".env"))

# ── Google ADK imports ─────────────────────────────────────────────────
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from mainAgent.agent import root_agent

# ── Flask App ──────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="frontend", static_url_path="")
CORS(app)

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

ATTENDANCE_SERVER = os.getenv("ATTENDANCE_SERVER_URL", "https://localhost:5001")


# ── Helper: Run agent ──────────────────────────────────────────────────
async def _run_agent(user_id: str, message: str) -> str:
    """Send a message to the root agent and collect the response."""
    # Get or create session
    if user_id not in user_sessions:
        session = await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
        )
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


def run_async(coro):
    """Run an async coroutine from sync context."""
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


# ══════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

# ── Chat ───────────────────────────────────────────────────────────────
@app.route("/api/chat", methods=["POST"])
def chat():
    """Send a message to the root agent and return the response."""
    data = request.get_json()
    message = data.get("message", "").strip()
    user_id = data.get("user_id", "default_user")

    if not message:
        return jsonify({"status": "error", "message": "Message is required."}), 400

    try:
        response = run_async(_run_agent(user_id, message))
        return jsonify({"status": "success", "response": response})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Agent error: {str(e)}"}), 500


# ── Prompt Generation ─────────────────────────────────────────────────
@app.route("/api/prompt/generate", methods=["POST"])
def generate_prompt():
    """Send an idea to the prompt_wizard agent and return the generated prompt."""
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


# ── Code Generation (Vibe Coder) ───────────────────────────────────────
@app.route("/api/code/generate", methods=["POST"])
def generate_code():
    """Send a code request to the vibe_coder agent via root agent."""
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


# ── Auth (Supabase Auth) ───────────────────────────────────────────────
@app.route("/api/auth/login", methods=["POST"])
def login():
    """Verify credentials via Supabase Auth."""
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"status": "error", "message": "Username and password required."}), 400

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_ANON_KEY")

    # Build email: if user types student code or name, append @nct.edu
    email = username if "@" in username else f"{username}@nct.edu"

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

        if auth_res.status_code == 200 and auth_data.get("access_token"):
            user_meta = auth_data.get("user", {}).get("user_metadata", {})
            display_name = user_meta.get("name", username)
            role = user_meta.get("role", "student")

            # Try to get display name from students table
            try:
                from mainAgent.sub_agents.university_agent.db.database import get_connection
                conn = get_connection()
                cur = conn.cursor()
                student_code = user_meta.get("student_code", username)
                cur.execute("SELECT name FROM students WHERE student_code = %s", (student_code,))
                row = cur.fetchone()
                if row:
                    display_name = row[0]
                conn.close()
            except Exception:
                pass

            return jsonify({
                "status": "success",
                "is_admin": role.lower() == "admin",
                "username": display_name,
                "role": role,
                "access_token": auth_data["access_token"],
            })
        else:
            msg = auth_data.get("error_description") or auth_data.get("msg") or "Invalid credentials"
            return jsonify({"status": "error", "message": msg}), 401

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Auth error: {str(e)}"}), 500



# ══════════════════════════════════════════════════════════════════════
# ATTENDANCE SERVER PROXY
# ══════════════════════════════════════════════════════════════════════

@app.route("/api/courses", methods=["GET"])
def proxy_courses():
    """Proxy: list courses from attendance server."""
    try:
        r = http_requests.get(f"{ATTENDANCE_SERVER}/api/courses", verify=False, timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/session/create", methods=["POST"])
def proxy_create_session():
    """Proxy: create attendance session."""
    try:
        r = http_requests.post(
            f"{ATTENDANCE_SERVER}/api/session/create",
            json=request.get_json(),
            verify=False,
            timeout=5,
        )
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/session/<code>", methods=["GET"])
def proxy_check_session(code):
    """Proxy: check session status."""
    try:
        r = http_requests.get(f"{ATTENDANCE_SERVER}/api/session/{code}", verify=False, timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/attendance/verify", methods=["POST"])
def proxy_verify_attendance():
    """Proxy: verify face and record attendance."""
    try:
        r = http_requests.post(
            f"{ATTENDANCE_SERVER}/api/attendance/verify",
            json=request.get_json(),
            verify=False,
            timeout=15,
        )
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/session/<code>/report", methods=["GET"])
def proxy_session_report(code):
    """Proxy: get attendance report."""
    try:
        r = http_requests.get(f"{ATTENDANCE_SERVER}/api/session/{code}/report", verify=False, timeout=5)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/session/<code>/close", methods=["POST"])
def proxy_close_session(code):
    """Proxy: close attendance session."""
    try:
        r = http_requests.post(f"{ATTENDANCE_SERVER}/api/session/{code}/close", verify=False, timeout=5)
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
        from mainAgent.sub_agents.university_agent.web.generate_cert import generate_self_signed_cert
        cert_dir = os.path.dirname(__file__)
        cert_path, key_path = generate_self_signed_cert(cert_dir)
        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_ctx.load_cert_chain(cert_path, key_path)
    except Exception as e:
        print(f"Warning: Could not generate SSL certs. Falling back to HTTP. {e}")
        ssl_ctx = None

    lan_ip = get_lan_ip()
    protocol = "https" if ssl_ctx else "http"

    print("\n" + "=" * 60)
    print("🚀 ChatNCT Server (Unified App)")
    print("=" * 60)
    print(f"  Local:      {protocol}://localhost:5000/")
    print(f"  Network:    {protocol}://{lan_ip}:5000/")
    print("=" * 60)
    print("⚠️  To test from mobile camera, you MUST open the Network link")
    print("   on your mobile and accept the 'Not Secure' warning.")
    print("=" * 60 + "\n")

    app.run(host="0.0.0.0", port=5000, debug=True, ssl_context=ssl_ctx)
