import os
import sys
import asyncio
import json
import re
import traceback
import threading
import warnings
import logging
import requests as http_requests
from datetime import datetime
from dotenv import load_dotenv
from queue import Queue
from functools import wraps

# Suppress urllib3 SSL warnings (we use self-signed certs for local dev)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

from flask import Flask, Response, request, jsonify, send_from_directory, stream_with_context
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
load_dotenv(os.path.join(os.path.dirname(__file__), "mainAgent", ".env"))

# ── Google ADK imports ─────────────────────────────────────────────────
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from mainAgent.agent import root_agent
from mainAgent.sub_agents.prompt_wizard.agent import root_agent as prompt_wizard_agent

# ── Database imports ───────────────────────────────────────────────────
from mainAgent.db.database import (
    get_connection, release_connection, run_migrations
)

# ── Flask App ──────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="frontend", static_url_path="")
CORS(app)

# ── Rate Limiter (W-12 fix: prevent API credit abuse) ─────────────────
# Uses in-memory storage (no Redis needed for a prototype).
# Limits are per-user based on IP address.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per minute"],      # Global default for all endpoints
    storage_uri="memory://",                 # In-memory — suitable for single-process
)

# ── Logging ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("chatnct")

# Disable caching for static files during development
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

@app.after_request
def add_no_cache_headers(response):
    """Prevent browsers from caching JS/HTML files during development."""
    if response.content_type and ('javascript' in response.content_type or 'html' in response.content_type):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
    return response

# ── Custom API Request/Response Logging & Error Tracking ───────────────
@app.before_request
def log_api_request():
    if request.path.startswith("/api/"):
        method = request.method
        path = request.path
        ip = request.remote_addr
        
        payload = None
        if request.is_json:
            try:
                raw_payload = request.get_json()
                if isinstance(raw_payload, dict):
                    payload = raw_payload.copy()
                    if "password" in payload:
                        payload["password"] = "********"
                    # Mask large base64 image strings from face/QR verification
                    for img_key in ["image", "photo", "frame", "face_image"]:
                        if img_key in payload and isinstance(payload[img_key], str) and len(payload[img_key]) > 100:
                            payload[img_key] = f"<Base64 Image: {len(payload[img_key])} chars>"
                else:
                    payload = raw_payload
            except Exception:
                payload = "<Invalid JSON>"
        
        logger.info(f"[REQ] {method} {path} | IP: {ip} | Payload: {payload}")

@app.after_request
def log_api_response(response):
    if request.path.startswith("/api/"):
        method = request.method
        path = request.path
        status = response.status_code
        logger.info(f"[RES] {method} {path} | Status: {status}")
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    status_code = 500
    if hasattr(e, "code"):
        status_code = e.code
        
    tb = traceback.format_exc()
    
    # Don't print massive tracebacks for standard 404 Not Found warnings
    if status_code == 404:
        logger.warning(f"[404] Not Found: {request.method} {request.path}")
        return jsonify({
            "status": "error",
            "code": "NOT_FOUND",
            "message": f"The requested URL was not found: {request.path}"
        }), 404

    # Log error message only (no traceback)
    logger.error(f"[ERROR] Exception on {request.method} {request.path}: {str(e)}")
    
    if hasattr(e, "code"):
        return jsonify({
            "status": "error",
            "code": "SERVER_ERROR",
            "message": str(e)
            # VULN-03 FIX: Removed traceback from client response
        }), e.code
        
    return jsonify({
        "status": "error",
        "code": "INTERNAL_SERVER_ERROR",
        "message": f"An unexpected error occurred: {str(e)}"
        # VULN-03 FIX: Removed traceback from client response
    }), 500

def is_greeting(message: str) -> bool:
    """Check if the user message is a simple greeting so we can respond instantly."""
    msg = message.strip().lower()
    for char in [".", ",", "!", "?", "؟", "-", "_"]:
        msg = msg.replace(char, "")
    msg = msg.strip()
    
    greetings = {
        "hi", "hello", "hey", "اهلا", "أهلا", "أهلاً", "ازيك", "إزيك", "سلام", "سلام عليكم", "السلام عليكم", 
        "صباح الخير", "مساء الخير", "منور", "يا فنان", "يا صديقي", "hi there", "hello there"
    }
    
    if msg in greetings:
        return True
        
    words = msg.split()
    if len(words) <= 3:
        for w in words:
            if w in greetings:
                return True
                
    return False

# Suppress verbose request logs (GET /img/Logo.png, etc.)
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

print("[STARTUP] Running database migrations...")
try:
    run_migrations()
    print("[STARTUP] Database migrations checks passed.")
except Exception as e:
    print(f"[STARTUP] Migration error (non-fatal): {e}")
    traceback.print_exc()

# ── ADK Session Management ────────────────────────────────────────────
import uuid as _uuid

APP_NAME = "chatnct"
PROMPT_APP_NAME = "chatnct_prompt"
_SESSIONS_DB = os.path.join(os.path.dirname(__file__), "sessions.db")

print("[STARTUP] Initializing ADK Session Services & Runners...")
try:
    session_service = DatabaseSessionService(db_url=f"sqlite+aiosqlite:///{_SESSIONS_DB}")
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )
    print(f"[STARTUP] Main Agent ADK Runner ready (app: {APP_NAME}, db: {_SESSIONS_DB})")
except Exception as e:
    print(f"[STARTUP] Error initializing Main Agent ADK Runner: {e}")
    traceback.print_exc()

try:
    prompt_session_service = DatabaseSessionService(db_url=f"sqlite+aiosqlite:///{_SESSIONS_DB}")
    prompt_runner = Runner(
        agent=prompt_wizard_agent,
        app_name=PROMPT_APP_NAME,
        session_service=prompt_session_service,
    )
    print(f"[STARTUP] Prompt Wizard ADK Runner ready (app: {PROMPT_APP_NAME})")
except Exception as e:
    print(f"[STARTUP] Error initializing Prompt Wizard ADK Runner: {e}")
    traceback.print_exc()


# Detect if running on Hugging Face Spaces (HF_SPACE is automatically set by Hugging Face)
if os.getenv("HF_SPACE") or os.getenv("SPACE_ID"):
    _DEFAULT_ATTENDANCE_URL = "http://127.0.0.1:5001"
else:
    _DEFAULT_ATTENDANCE_URL = "https://127.0.0.1:5001"

ATTENDANCE_SERVER = os.getenv("ATTENDANCE_SERVER_URL", _DEFAULT_ATTENDANCE_URL)




# ── Persistent Event Loop (Feature 9: Performance) ────────────────────
_loop = asyncio.new_event_loop()
_loop_thread = threading.Thread(target=_loop.run_forever, daemon=True)
_loop_thread.start()


# Configurable timeout (W-08 fix): default 120s, override via AGENT_TIMEOUT env var
_AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "120"))


def run_async(coro, timeout=None):
    """Run an async coroutine on the persistent event loop.

    Uses a configurable timeout (default from AGENT_TIMEOUT env var).
    Logs a warning if the operation times out instead of silently hanging.
    """
    if timeout is None:
        timeout = _AGENT_TIMEOUT
    future = asyncio.run_coroutine_threadsafe(coro, _loop)
    try:
        return future.result(timeout=timeout)
    except TimeoutError:
        future.cancel()
        logger.error("run_async timed out after %ds — cancelling coroutine", timeout)
        raise TimeoutError(f"Agent did not respond within {timeout}s. Please try again.")


def _resolve_student_info(user_id: str) -> tuple:
    """Resolve (student_code, student_name, role) from profiles table given user_id."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        # 1. Check if user_id is already the student_code
        cur.execute("SELECT student_code, name, role FROM profiles WHERE student_code = %s", (user_id,))
        row = cur.fetchone()
        if row:
            return str(row["student_code"]), str(row.get("name", "")), str(row.get("role", "student"))
        
        # 2. Check if user_id is the database UUID (id)
        cur.execute("SELECT student_code, name, role FROM profiles WHERE id::text = %s", (user_id,))
        row = cur.fetchone()
        if row:
            return str(row["student_code"]), str(row.get("name", "")), str(row.get("role", "student"))
            
        return user_id, "", "student"
    except Exception:
        return user_id, "", "student"
    finally:
        release_connection(conn)


_SEARCH_TRIGGER_PATTERNS = [
    r"\bsearch\b",
    r"\bgoogle\b",
    r"\blookup\b",
    r"\blook up\b",
    r"\bfind\b",
    r"سيرش",
    r"سرش",
    r"سريش",
    r"ابحث",
    r"دور",
    r"دوّر",
    r"شوفلي",
]


def _should_force_search(message: str) -> bool:
    """Return True when the user explicitly asks to search the web."""
    text = (message or "").strip().lower()
    if not text:
        return False
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in _SEARCH_TRIGGER_PATTERNS)


# ── Code Generation Detection ─────────────────────────────────────────
# Patterns that indicate the user pasted a code generation prompt
# (typically from the Prompt Generator page).
_CODE_PERSONA_PATTERN = re.compile(
    r"you are (?:a |an )?(?:senior|expert|professional|experienced|skilled|master)",
    re.IGNORECASE,
)
_CODE_KEYWORD_PATTERNS = [
    r"(?:build|create|develop|implement|write|code|generate|produce)\b.*\b(?:game|app|application|project|website|program|software|api|tool|script|bot)",
    r"Implementation Blueprint",
    r"Project Overview",
    r"Tech Stack",
    r"Folder Structure",
    r"Build Steps",
    r"requirements\.txt",
    r"```(?:python|javascript|typescript|bash|html|css|java|c\+\+|cpp|go|rust)",
]


def _should_force_code(message: str) -> bool:
    """Return True when the message looks like a code-generation prompt.

    Detects two main patterns:
      1. Expert persona prompt + coding keywords (from Prompt Generator)
      2. Project blueprint / implementation plan with code blocks
    """
    text = (message or "").strip()
    if not text:
        return False

    # Pattern 1: persona + coding keywords
    if _CODE_PERSONA_PATTERN.search(text):
        if any(re.search(kw, text, re.IGNORECASE) for kw in _CODE_KEYWORD_PATTERNS):
            return True

    # Pattern 2: multiple blueprint keywords present
    blueprint_hits = sum(
        1 for kw in _CODE_KEYWORD_PATTERNS
        if re.search(kw, text, re.IGNORECASE)
    )
    if blueprint_hits >= 3:
        return True

    return False


import re

def _build_contextual_message(user_id: str, message: str) -> str:
    # VULN-04 FIX: Sanitize message to prevent tag injection (e.g., [USER_ROLE: ...])
    sanitized_message = re.sub(r'\[.*?\]', '', message)
    
    resolved_code, resolved_name, resolved_role = _resolve_student_info(user_id)
    prefixes = [f"[STUDENT_CODE: {resolved_code}]"]
    if resolved_name:
        prefixes.append(f"[STUDENT_NAME: {resolved_name}]")
    if resolved_role:
        prefixes.append(f"[USER_ROLE: {resolved_role}]")
    if _should_force_search(sanitized_message):
        prefixes.append("[FORCE_SEARCH: true]")
    if _should_force_code(sanitized_message):
        prefixes.append("[FORCE_CODE: true]")
    prefixes.append(sanitized_message)
    return "\n".join(prefixes)


# ── Helper: Run agent ──────────────────────────────────────────────────
async def _run_agent(user_id: str, message: str, chat_session_id: str = None) -> str:
    """Send a message to the root agent and collect the response.

    When *chat_session_id* is provided it is used as the ADK session_id so that
    each PostgreSQL chat session keeps its own isolated agent context.
    """
    session_id = chat_session_id or str(_uuid.uuid4())

    # Ensure a session object exists (idempotent – first call creates it)
    try:
        session_result = session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id,
        )
        import inspect
        if inspect.iscoroutine(session_result):
            session = await session_result
        else:
            session = session_result
    except Exception:
        session = None

    if session is None:
        session_result = session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id,
        )
        import inspect
        if inspect.iscoroutine(session_result):
            await session_result
        else:
            pass  # already created synchronously

    contextual_message = _build_contextual_message(user_id, message)

    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=contextual_message)],
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


# ── Direct Prompt Wizard (bypasses root agent) ─────────────────────────
async def _run_prompt_wizard(user_id: str, idea: str) -> str:
    """Call the prompt_wizard agent directly — no root agent in the middle.

    Each invocation creates a fresh session (UUID) to prevent prompt history
    from leaking between different generation requests.
    """
    session_id = str(_uuid.uuid4())
    session_result = prompt_session_service.create_session(
        app_name=PROMPT_APP_NAME,
        user_id=user_id,
        session_id=session_id,
    )
    import inspect
    if inspect.iscoroutine(session_result):
        await session_result

    # Send a clean, direct instruction to prompt_wizard
    prompt_message = f"Generate a professional master prompt for this idea: {idea}"

    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt_message)],
    )

    response_parts = []
    async for event in prompt_runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    response_parts.append(part.text)

    raw = "\n".join(response_parts) if response_parts else ""

    # ── Server-side cleanup: strip markdown code fences & conversational filler ──
    cleaned = raw.strip()

    # Remove ```markdown or ``` wrapper if present
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1:]
        else:
            cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    # Remove any leading chatter lines before the actual prompt body
    # Patterns like "Here is your prompt:", "Sure! Here you go:", etc.
    chatter_patterns = [
        r"^(?:here(?:'s| is| you go).*?[:!]?\s*\n)",
        r"^(?:sure[!,.]?\s*(?:here.*?)?[:!]?\s*\n)",
        r"^(?:of course[!,.]?\s*(?:here.*?)?[:!]?\s*\n)",
        r"^(?:absolutely[!,.]?\s*(?:here.*?)?[:!]?\s*\n)",
        r"^(?:اتفضل.*?\n)",
        r"^(?:تفضل.*?\n)",
        r"^(?:اهو.*?\n)",
        r"^(?:ده ال.*?prompt.*?\n)",
    ]
    for pattern in chatter_patterns:
        cleaned = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE)
    cleaned = cleaned.strip()

    # Remove any trailing chatter after the prompt
    trailing_patterns = [
        r"\n(?:feel free|let me know|hope this helps|if you need|you can use).*$",
        r"\n(?:لو عايز|لو محتاج|ممكن تستخدم|تقدر تستخدم).*$",
    ]
    for pattern in trailing_patterns:
        cleaned = re.sub(pattern, "", cleaned, count=1, flags=re.IGNORECASE | re.DOTALL)
    cleaned = cleaned.strip()

    return cleaned if cleaned else raw.strip()



async def _stream_agent(user_id: str, message: str, queue: Queue, chat_session_id: str = None) -> str:
    """Send agent text parts to a queue as they arrive.

    Uses *chat_session_id* (when provided) as the ADK session_id for
    context isolation — same strategy as _run_agent.
    """
    session_id = chat_session_id or str(_uuid.uuid4())

    # Ensure a session object exists
    try:
        session_result = session_service.get_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id,
        )
        import inspect
        if inspect.iscoroutine(session_result):
            session = await session_result
        else:
            session = session_result
    except Exception:
        session = None

    if session is None:
        session_result = session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id,
        )
        import inspect
        if inspect.iscoroutine(session_result):
            await session_result

    contextual_message = _build_contextual_message(user_id, message)

    content = types.Content(
        role="user",
        parts=[types.Part.from_text(text=contextual_message)],
    )

    response_parts = []
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                # Check for tool/function calls to update the waiting status dynamically
                try:
                    if hasattr(part, "function_call") and part.function_call:
                        name = part.function_call.name
                        args = part.function_call.args
                        args_dict = {}
                        if args:
                            try:
                                args_dict = dict(args)
                            except Exception:
                                if hasattr(args, "items"):
                                    args_dict = {k: v for k, v in args.items()}
                        
                        status_msg = None
                        if name == "search_material":
                            q = args_dict.get("query", "")
                            status_msg = f"Searching lectures for '{q}'" if q else "Searching lecture files"
                        elif name == "get_all_materials_info":
                            status_msg = "Reviewing available lectures list"
                        elif name == "get_available_subjects":
                            status_msg = "Checking available subjects"
                        elif name == "generate_project_blueprint":
                            req = args_dict.get("requirement", "")
                            short_req = (req[:30] + "...") if req and len(req) > 30 else req
                            status_msg = f"Planning blueprint for '{short_req}'" if req else "Planning project blueprint"
                        elif name == "generate_code_files":
                            req = args_dict.get("requirement", "")
                            short_req = (req[:30] + "...") if req and len(req) > 30 else req
                            status_msg = f"Generating code for '{short_req}'" if req else "Writing code files"
                        elif name == "debug_code_issue":
                            err = args_dict.get("error_message", "")
                            short_err = (err[:30] + "...") if err and len(err) > 30 else err
                            status_msg = f"Debugging code issue '{short_err}'" if err else "Analyzing code for bugs"
                        elif name == "search_data":
                            q = args_dict.get("query", "")
                            short_q = (q[:35] + "...") if q and len(q) > 35 else q
                            status_msg = f"Searching university rules for '{short_q}'" if q else "Checking student affairs rules"
                        elif name == "duckduckgo_search_tool":
                            q = args_dict.get("query", "")
                            short_q = (q[:35] + "...") if q and len(q) > 35 else q
                            status_msg = f"Searching the web for '{short_q}'" if q else "Searching the web"
                        elif name == "get_student_attendance_summary":
                            status_msg = "Calculating attendance & absences summary"
                        elif name == "get_course_session_log":
                            course = args_dict.get("course_code_or_name", "")
                            status_msg = f"Reviewing attendance log for {course}" if course else "Reviewing attendance logs"
                        elif name == "get_missed_lectures":
                            status_msg = "Checking missed lectures list"
                        elif name == "get_missed_lecture_summaries":
                            status_msg = "Generating missed lecture summaries"
                        elif name == "transfer_to_agent":
                            target = args_dict.get("agent_name", args_dict.get("target_agent_name", ""))
                            status_msg = f"Routing request to {target}" if target else "Routing request"
                        elif name == "study_agent":
                            status_msg = "Accessing study assistant"
                        elif name == "vibe_coder_agent":
                            status_msg = "Opening code builder"
                        elif name == "search_agent":
                            status_msg = "Accessing web search tools"
                        elif name == "student_chatbot":
                            status_msg = "Accessing student affairs"
                        elif name == "academic_analyzer":
                            status_msg = "Analyzing academic records"
                        elif name == "prompt_wizard":
                            status_msg = "Opening Prompt Wizard"

                        if status_msg:
                            queue.put({"type": "status", "status": status_msg})
                except Exception:
                    pass

                if part.text:
                    response_parts.append(part.text)
                    queue.put({"type": "delta", "text": part.text})

    return "\n".join(response_parts) if response_parts else "عذرًا، مفيش رد متاح دلوقتي."


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
def _create_chat_session(user_id: str, message: str) -> str:
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
        return chat_session_id
    finally:
        release_connection(conn)


def _save_chat_message(chat_session_id: str, role: str, content: str) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (%s, %s, %s)",
            (chat_session_id, role, content)
        )
        conn.commit()
    finally:
        release_connection(conn)


# ── Auth Decorator ─────────────────────────────────────────────────────
def token_required(f):
    """Validate Supabase JWT from 'Authorization: Bearer <token>' header.

    Injects `current_user_id` (the verified Supabase UUID) into route kwargs.
    Returns 401 if the token is missing or invalid, 500 on auth-service failure.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("[AUTH] Access denied: Missing or invalid 'Bearer' prefix in Authorization header.")
            return jsonify({
                "status": "error",
                "code": "MISSING_TOKEN",
                "message": "Authorization token is required.",
            }), 401

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            logger.warning("[AUTH] Access denied: Authorization token is empty after Bearer prefix.")
            return jsonify({
                "status": "error",
                "code": "MISSING_TOKEN",
                "message": "Authorization token is required.",
            }), 401

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        try:
            res = http_requests.get(
                f"{supabase_url}/auth/v1/user",
                headers={
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {token}",
                },
                timeout=10,
            )

            if res.status_code != 200:
                logger.warning(f"[AUTH] Access denied: Supabase auth validation failed with status {res.status_code}. Response: {res.text.strip()}")
                return jsonify({
                    "status": "error",
                    "code": "INVALID_TOKEN",
                    "message": "Invalid or expired token. Please log in again.",
                }), 401

            user_data = res.json()
            current_user_id = user_data.get("id")

            if not current_user_id:
                logger.warning("[AUTH] Access denied: User ID missing from Supabase user payload.")
                return jsonify({
                    "status": "error",
                    "code": "INVALID_TOKEN",
                    "message": "Could not extract user identity from token.",
                }), 401

        except Exception as e:
            logger.error(f"[AUTH] Auth service exception: {str(e)}", exc_info=True)
            return jsonify({
                "status": "error",
                "code": "AUTH_SERVICE_ERROR",
                "message": f"Auth service error: {str(e)}",
            }), 500

        # Inject the verified UUID into the route — never trust client-provided IDs
        kwargs["current_user_id"] = current_user_id
        return f(*args, **kwargs)

    return decorated


def _verify_session_ownership(session_id: str, user_uuid: str) -> bool:
    """Return True if the chat session belongs to the authenticated user.

    Checks both the raw Supabase UUID and the associated student_code to handle
    sessions that may have been created before the auth decorator was enforced.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        # Resolve the student_code linked to this UUID
        cur.execute(
            "SELECT student_code FROM profiles WHERE id::text = %s",
            (user_uuid,),
        )
        row = cur.fetchone()
        student_code = str(row["student_code"]) if row and row.get("student_code") else None

        if student_code:
            cur.execute(
                "SELECT 1 FROM chat_sessions"
                " WHERE id = %s AND (student_id = %s OR student_id = %s)",
                (session_id, user_uuid, student_code),
            )
        else:
            cur.execute(
                "SELECT 1 FROM chat_sessions WHERE id = %s AND student_id = %s",
                (session_id, user_uuid),
            )
        return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        release_connection(conn)


def instructor_required(f):
    """Ensure the user is an instructor or admin."""
    @wraps(f)
    def decorated(*args, **kwargs):
        current_user_id = kwargs.get("current_user_id")
        if not current_user_id:
            return jsonify({"status": "error", "code": "UNAUTHORIZED", "message": "User identity missing."}), 401
        
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT role FROM profiles WHERE id::text = %s", (current_user_id,))
            row = cur.fetchone()
            if not row or row["role"] not in ("instructor", "admin"):
                return jsonify({"status": "error", "code": "FORBIDDEN", "message": "Instructor privileges required."}), 403
        finally:
            release_connection(conn)
            
        return f(*args, **kwargs)
    return decorated


# API ENDPOINTS
# ══════════════════════════════════════════════════════════════════════

# ── Chat (with Supabase persistence — Feature 1) ──────────────────────
@app.route("/api/chat", methods=["POST"])
@limiter.limit("20 per minute")   # W-12: rate limit chat to prevent credit abuse
@token_required
def chat(current_user_id: str):
    """Send a message to the root agent and return the response. Saves to DB."""
    data = request.get_json()
    message = data.get("message", "").strip()
    chat_session_id = data.get("session_id", None)  # Supabase chat_sessions.id

    if not message:
        return jsonify({"status": "error", "code": "MISSING_MESSAGE", "message": "Message is required."}), 400

    try:
        # Create a new session, or verify ownership of an existing one (IDOR fix)
        if not chat_session_id:
            chat_session_id = _create_chat_session(current_user_id, message)
        elif not _verify_session_ownership(chat_session_id, current_user_id):
            return jsonify({"status": "error", "code": "FORBIDDEN", "message": "Access denied to this session."}), 403

        # Save user message
        _save_chat_message(chat_session_id, "user", message)

        # Check for instant greeting response
        if is_greeting(message):
            resolved_code, resolved_name, resolved_role = _resolve_student_info(current_user_id)
            if resolved_role in ("instructor", "admin"):
                response = f"أهلاً بحضرتك يا دكتور {resolved_name if resolved_name else ''}. كيف يمكنني مساعدة سيادتك اليوم؟"
            else:
                response = "أهلاً يا فنان! منور ChatNCT. أقدر أساعدك إزاي النهاردة في المنهج أو أي حاجة تانية؟"
            _save_chat_message(chat_session_id, "bot", response)
            return jsonify({
                "status": "success",
                "response": response,
                "session_id": chat_session_id,
            })

        # Get agent response (UUID passed; _build_contextual_message resolves student_code)
        response = run_async(_run_agent(current_user_id, message, chat_session_id=chat_session_id))

        # Save bot response
        _save_chat_message(chat_session_id, "bot", response)

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
@app.route("/api/chat/stream", methods=["POST"])
@limiter.limit("20 per minute")   # W-12: rate limit streaming chat
@token_required
def chat_stream(current_user_id: str):
    """Stream agent text parts as newline-delimited JSON for a faster chat feel."""
    data = request.get_json()
    message = data.get("message", "").strip()
    chat_session_id = data.get("session_id", None)

    if not message:
        return jsonify({"status": "error", "code": "MISSING_MESSAGE", "message": "Message is required."}), 400

    try:
        # Create a new session, or verify ownership of an existing one (IDOR fix)
        if not chat_session_id:
            chat_session_id = _create_chat_session(current_user_id, message)
        elif not _verify_session_ownership(chat_session_id, current_user_id):
            return jsonify({"status": "error", "code": "FORBIDDEN", "message": "Access denied to this session."}), 403
        _save_chat_message(chat_session_id, "user", message)
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "code": "DB_ERROR",
            "message": f"Database error: {str(e)}",
        }), 500

    def encode_event(payload):
        return json.dumps(payload, ensure_ascii=False) + "\n"

    @stream_with_context
    def generate():
        queue = Queue()
        yield encode_event({"type": "meta", "session_id": chat_session_id})

        if is_greeting(message):
            resolved_code, resolved_name, resolved_role = _resolve_student_info(current_user_id)
            if resolved_role in ("instructor", "admin"):
                response_text = f"أهلاً بحضرتك يا دكتور {resolved_name if resolved_name else ''}. كيف يمكنني مساعدة سيادتك اليوم؟"
            else:
                response_text = "أهلاً يا فنان! منور ChatNCT. أقدر أساعدك إزاي النهاردة في المنهج أو أي حاجة تانية؟"
            yield encode_event({"type": "delta", "text": response_text})
            _save_chat_message(chat_session_id, "bot", response_text)
            yield encode_event({"type": "done"})
            return

        async def run_and_finish():
            try:
                response_text = await _stream_agent(current_user_id, message, queue, chat_session_id=chat_session_id)
                if not response_text:
                    response_text = "عذرًا، مفيش رد متاح دلوقتي."
                _save_chat_message(chat_session_id, "bot", response_text)
                queue.put({"type": "done"})
            except Exception as exc:
                traceback.print_exc()
                queue.put({"type": "error", "message": f"Agent error: {str(exc)}"})

        future = asyncio.run_coroutine_threadsafe(run_and_finish(), _loop)
        try:
            while True:
                item = queue.get()
                yield encode_event(item)
                if item.get("type") in {"done", "error"}:
                    break
        finally:
            if not future.done():
                future.cancel()

    return Response(
        generate(),
        mimetype="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/chat/sessions", methods=["GET"])
@token_required
def list_chat_sessions(current_user_id: str):
    """List chat sessions for the authenticated user with pagination."""
    page = max(1, int(request.args.get("page", 1)))
    # VULN-10 FIX: Cap per_page to a maximum of 50 to prevent DoS
    per_page = min(max(1, int(request.args.get("per_page", 20))), 50)
    offset = (page - 1) * per_page

    conn = get_connection()
    try:
        cur = conn.cursor()
        # Resolve the student_code so sessions stored under either identifier are found
        cur.execute(
            "SELECT student_code FROM profiles WHERE id::text = %s",
            (current_user_id,),
        )
        row = cur.fetchone()
        student_code = str(row["student_code"]) if row and row.get("student_code") else None

        if student_code:
            cur.execute(
                "SELECT COUNT(*) FROM chat_sessions"
                " WHERE student_id = %s OR student_id = %s",
                (current_user_id, student_code),
            )
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT id, title, created_at FROM chat_sessions
                WHERE student_id = %s OR student_id = %s
                ORDER BY created_at DESC LIMIT %s OFFSET %s
            """, (current_user_id, student_code, per_page, offset))
        else:
            cur.execute(
                "SELECT COUNT(*) FROM chat_sessions WHERE student_id = %s",
                (current_user_id,),
            )
            total = cur.fetchone()[0]
            cur.execute("""
                SELECT id, title, created_at FROM chat_sessions
                WHERE student_id = %s ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, (current_user_id, per_page, offset))

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
@token_required
def get_chat_messages(session_id, current_user_id: str):
    """Get messages for a chat session with pagination (ownership enforced)."""
    if not _verify_session_ownership(session_id, current_user_id):
        return jsonify({"status": "error", "code": "FORBIDDEN", "message": "Access denied to this session."}), 403

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
@token_required
def delete_chat_session(session_id, current_user_id: str):
    """Delete a chat session and all its messages (ownership enforced)."""
    if not _verify_session_ownership(session_id, current_user_id):
        return jsonify({"status": "error", "code": "FORBIDDEN", "message": "Access denied to this session."}), 403

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
@token_required
def rename_chat_session(session_id, current_user_id: str):
    """Rename a chat session (ownership enforced)."""
    if not _verify_session_ownership(session_id, current_user_id):
        return jsonify({"status": "error", "code": "FORBIDDEN", "message": "Access denied to this session."}), 403

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
@limiter.limit("10 per minute")   # W-12: rate limit prompt generation
@token_required
def generate_prompt(current_user_id: str):
    data = request.get_json()
    idea = data.get("idea", "").strip()
    user_id = data.get("user_id", "prompt_user")

    if not idea:
        return jsonify({"status": "error", "message": "Idea is required."}), 400

    try:
        # Call prompt_wizard DIRECTLY — bypasses the root agent entirely
        response = run_async(_run_prompt_wizard(user_id, idea))
        return jsonify({"status": "success", "prompt": response})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Agent error: {str(e)}"}), 500


# ── Code Generation (Vibe Coder) ──────────────────────────────────────
@app.route("/api/code/generate", methods=["POST"])
@limiter.limit("10 per minute")   # W-12: rate limit code generation
@token_required # VULN-02 FIX: Require authentication
def generate_code(current_user_id: str):
    data = request.get_json()
    prompt = data.get("prompt", "").strip()
    
    # Use authenticated user ID instead of client-provided one
    user_id = current_user_id

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
@limiter.limit("5 per minute") # VULN-05 FIX: Rate limit login attempts
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
@token_required
def get_courses(current_user_id: str):
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
@token_required
@instructor_required
def proxy_create_session(current_user_id: str):
    """Proxy to attendance server with retry (server may still be loading models on first call)."""
    import time as _time
    last_err = None
    for attempt in range(3):
        try:
            r = http_requests.post(
                f"{ATTENDANCE_SERVER}/api/session/create",
                json=request.get_json(),
                verify=False, timeout=20,
            )
            return jsonify(r.json()), r.status_code
        except Exception as e:
            last_err = e
            if attempt < 2:
                _time.sleep(5)   # wait 5s then retry
    return jsonify({"status": "error", "message": f"Attendance server unreachable: {last_err}"}), 502



@app.route("/api/session/<code>", methods=["GET"])
@token_required
def proxy_check_session(code, current_user_id: str):
    try:
        r = http_requests.get(f"{ATTENDANCE_SERVER}/api/session/{code}", verify=False, timeout=15)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/session/<code>/qr-token", methods=["GET"])
@token_required
@instructor_required
def proxy_qr_token(code, current_user_id: str):
    """Proxy: get rotating QR token."""
    try:
        r = http_requests.get(f"{ATTENDANCE_SERVER}/api/session/{code}/qr-token", verify=False, timeout=15)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/attendance/verify", methods=["POST"])
@token_required
def proxy_verify_attendance(current_user_id: str):
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
@token_required
def proxy_check_identity(current_user_id: str):
    try:
        r = http_requests.post(
            f"{ATTENDANCE_SERVER}/api/attendance/check_identity",
            json=request.get_json(),
            verify=False, timeout=120,
        )
        resp_data = r.json()
        return jsonify(resp_data), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server unreachable: {e}"}), 502


@app.route("/api/attendance/check_pose", methods=["POST"])
@token_required
def proxy_check_pose(current_user_id: str):
    try:
        r = http_requests.post(
            f"{ATTENDANCE_SERVER}/api/attendance/check_pose",
            json=request.get_json(),
            verify=False, timeout=10,
        )
        resp_data = r.json()
        return jsonify(resp_data), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Server unreachable: {e}"}), 502


@app.route("/api/attendance/challenges", methods=["GET"])
@token_required
def proxy_challenges(current_user_id: str):
    """Proxy: get liveness challenges."""
    try:
        r = http_requests.get(f"{ATTENDANCE_SERVER}/api/attendance/challenges", verify=False, timeout=15)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/attendance/prepare", methods=["POST"])
@token_required
def proxy_prepare(current_user_id: str):
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
@token_required
@instructor_required
def proxy_session_report(code, current_user_id: str):
    try:
        r = http_requests.get(f"{ATTENDANCE_SERVER}/api/session/{code}/report", verify=False, timeout=15)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"status": "error", "message": f"Attendance server unreachable: {e}"}), 502


@app.route("/api/session/<code>/close", methods=["POST"])
@token_required
@instructor_required
def proxy_close_session(code, current_user_id: str):
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

    print(f"Local URL:      {protocol}://localhost:5000/")
    print(f"Network URL:    {protocol}://{lan_ip}:5000/")
    print("[INFO] Serving frontend and API requests...")
    print("[INFO] Press Ctrl+C in this terminal to stop the server.")

    try:
        app.run(host="0.0.0.0", port=5000, use_reloader=False, ssl_context=ssl_ctx)
    except OSError as os_err:
        print(f"[CRITICAL] OSError starting server: {os_err}")
        if "address already in use" in str(os_err).lower() or os_err.errno in (98, 10048):
            print("[CRITICAL] PORT 5000 IS ALREADY OCCUPIED!")
            print("Another process is running on this port. To fix this:")
            print("- Run 'Stop-Process -Name python -Force' in PowerShell")
            print("- Or run 'taskkill /IM python.exe /F' in CMD")
            print("Then try starting this server again.")
        else:
            traceback.print_exc()
    except Exception as e:
        print(f"[CRITICAL] Exception starting server: {e}")
        traceback.print_exc()
