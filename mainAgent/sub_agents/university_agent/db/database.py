"""PostgreSQL database — provides connections to Supabase."""

import os
import psycopg2
from psycopg2.extras import DictCursor
from dotenv import load_dotenv

# Try to find the .env file in the mainAgent directory
_DIR = os.path.dirname(os.path.dirname(__file__)) # university_agent
_MAIN_AGENT_DIR = os.path.dirname(os.path.dirname(_DIR)) # mainAgent
env_path = os.path.join(_MAIN_AGENT_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv() # Fallback

def get_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set in the environment variables.")
    
    conn = psycopg2.connect(db_url, cursor_factory=DictCursor)
    return conn
