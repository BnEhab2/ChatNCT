"""
database.py - Database Connection Manager

This file manages the connection to our PostgreSQL database (hosted on Supabase).
Instead of opening a new database connection every time someone makes a request,
we use a "connection pool" - a set of pre-opened connections that get reused.
This is much faster and more efficient.

Main functions:
  - get_connection()     : Borrow a database connection from the pool
  - release_connection() : Return a connection back to the pool when done
  - run_migrations()     : Create any missing database tables on startup
"""

import os
import psycopg2
from psycopg2.extras import DictCursor
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv

# ── Load Environment Variables ─────────────────────────────────────────
# Navigate from this file's location up to the project root to find .env
# Path: mainAgent/db/database.py -> mainAgent/db -> mainAgent -> project root
_DIR = os.path.dirname(__file__)
_MAIN_AGENT_DIR = os.path.dirname(_DIR)
_ROOT_DIR = os.path.dirname(_MAIN_AGENT_DIR)
_env_path = os.path.join(_ROOT_DIR, ".env")

if os.path.exists(_env_path):
    load_dotenv(_env_path)      # Load from project root .env file
else:
    load_dotenv()               # Fallback: look for .env in current directory


# ── Connection Pool ────────────────────────────────────────────────────
# The pool starts empty (None) and gets created on first use.
# It maintains between 1 and 10 connections to the database.
_pool = None


def _get_pool():
    """
    Create the connection pool if it doesn't exist yet (lazy initialization).
    Reads the DATABASE_URL from environment variables to know where to connect.
    """
    global _pool
    if _pool is None:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL is not set in the environment variables.")

        # ThreadedConnectionPool is thread-safe, meaning multiple requests
        # can safely borrow connections at the same time.
        # min=1 connection, max=10 connections, DictCursor returns rows as dicts
        _pool = ThreadedConnectionPool(1, 10, db_url, cursor_factory=DictCursor)
    return _pool


def get_connection():
    """Borrow a database connection from the pool. Remember to release it when done!"""
    return _get_pool().getconn()


def release_connection(conn):
    """
    Return a connection back to the pool so it can be reused.
    If something goes wrong, close the connection entirely as a fallback.
    """
    try:
        _get_pool().putconn(conn)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass


# ── Database Schema (Tables) ──────────────────────────────────────────
# These SQL statements create the tables our app needs.
# "IF NOT EXISTS" means they're safe to run multiple times - they won't
# duplicate tables that already exist.

_MIGRATIONS = """
-- Chat sessions: Each conversation a student starts with the AI
CREATE TABLE IF NOT EXISTS chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'New Chat',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_student ON chat_sessions(student_id);

-- Chat messages: Individual messages within a chat session
CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'bot')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id, created_at);

-- QR tokens: One-time-use tokens embedded in attendance QR codes
CREATE TABLE IF NOT EXISTS qr_tokens (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    used BOOLEAN NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS idx_qr_tokens_token ON qr_tokens(token);
CREATE INDEX IF NOT EXISTS idx_qr_tokens_session ON qr_tokens(session_id);

-- Rate limiting: Prevents students from spamming attendance attempts
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

-- Device binding: Links a student to a specific device per session
-- Prevents one person from marking attendance for multiple students
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

-- Speed up lookups on existing tables (attendance & students)
CREATE INDEX IF NOT EXISTS idx_attendance_student_session ON attendance(student_id, session_id);
CREATE INDEX IF NOT EXISTS idx_attendance_sessions_code ON attendance_sessions(session_code);
CREATE INDEX IF NOT EXISTS idx_attendance_sessions_active ON attendance_sessions(is_active, course_id);
CREATE INDEX IF NOT EXISTS idx_profiles_id ON profiles(id);
"""


def run_migrations():
    """
    Create all required database tables if they don't already exist.
    This runs once when the server starts up.
    Safe to run multiple times (idempotent) - won't break existing data.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(_MIGRATIONS)
        conn.commit()
        print(" Database migrations applied.")
    except Exception as e:
        # If something goes wrong, undo any partial changes
        conn.rollback()
        print(f"[WARNING] Migration warning: {e}")
    finally:
        # Always return the connection to the pool, even if there was an error
        release_connection(conn)
