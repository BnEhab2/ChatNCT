"""SQLite database — loads schema from schema.sql and provides connections."""

import sqlite3, os

_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(_DIR, "university.db")
SCHEMA_PATH = os.path.join(_DIR, "schema.sql")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_database():
    """Read schema.sql and execute it to create all tables and seed data.

    Uses a raw connection (FK OFF) because the INSERT order in schema.sql
    may reference tables whose data hasn't been inserted yet.
    """
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(schema_sql)
    conn.close()


init_database()
