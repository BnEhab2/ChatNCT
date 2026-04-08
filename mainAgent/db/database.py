"""PostgreSQL database — provides connections to Supabase with connection pooling."""

import os
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

# Try to find the .env file in the project root
_DIR = os.path.dirname(__file__)           # mainAgent/db
_MAIN_AGENT_DIR = os.path.dirname(_DIR)     # mainAgent
_ROOT_DIR = os.path.dirname(_MAIN_AGENT_DIR)  # project root
for _p in [os.path.join(_ROOT_DIR, ".env"), os.path.join(_MAIN_AGENT_DIR, ".env")]:
    if os.path.exists(_p):
        load_dotenv(_p)
        break
else:
    load_dotenv()

# ── Connection Pool ────────────────────────────────────────────────────
_pool = None


def _get_pool():
    global _pool
    if _pool is None:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL is not set in the environment variables.")
        _pool = ThreadedConnectionPool(1, 10, db_url, cursor_factory=DictCursor)
    return _pool


def get_connection():
    """Get a connection from the pool."""
    return _get_pool().getconn()


def release_connection(conn):
    """Return a connection to the pool."""
    try:
        _get_pool().putconn(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


# ── Schema Migration ───────────────────────────────────────────────────
_MIGRATIONS = """
-- Chat sessions
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'New Chat',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_student ON chat_sessions(student_id);

-- Chat messages
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'bot')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, created_at);

-- QR tokens
CREATE TABLE IF NOT EXISTS qr_tokens (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    used BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_qr_tokens_token ON qr_tokens(token);
CREATE INDEX IF NOT EXISTS idx_qr_tokens_session ON qr_tokens(session_id);

-- Rate limiting
CREATE TABLE IF NOT EXISTS rate_limits (
    id SERIAL PRIMARY KEY,
    student_id TEXT NOT NULL,
    session_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 1,
    blocked_until TIMESTAMPTZ,
    last_attempt TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rate_limits_lookup ON rate_limits(student_id, session_id, action);

-- Device binding
CREATE TABLE IF NOT EXISTS device_bindings (
    id SERIAL PRIMARY KEY,
    student_id TEXT NOT NULL,
    session_id INTEGER NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    device_fingerprint TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(student_id, session_id)
);

-- Performance indexes on existing tables
CREATE INDEX IF NOT EXISTS idx_attendance_student_session ON attendance(student_id, session_id);
CREATE INDEX IF NOT EXISTS idx_attendance_sessions_code ON attendance_sessions(session_code);
CREATE INDEX IF NOT EXISTS idx_attendance_sessions_active ON attendance_sessions(is_active, course_id);
CREATE INDEX IF NOT EXISTS idx_students_id ON students(id);
"""


def run_migrations():
    """Run schema migrations (idempotent)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_MIGRATIONS)
        conn.commit()
        print("✅ Database migrations applied.")
    except Exception as e:
        conn.rollback()
        print(f"⚠️  Migration warning: {e}")
    finally:
        release_connection(conn)
