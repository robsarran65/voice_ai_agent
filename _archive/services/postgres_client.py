# ============================================================
# Postgres Client (pgvector)
# Voice AI Agent (Low/No-Cost Edition)
# ============================================================

import os
import psycopg2
from psycopg2.extras import RealDictCursor

# ------------------------------------------------------------
# Environment Variables
# ------------------------------------------------------------
POSTGRES_URL = os.getenv("POSTGRES_URL")  # Example: postgres://user:pass@host/db


# ------------------------------------------------------------
# Connect to Postgres
# ------------------------------------------------------------
def get_connection():
    try:
        conn = psycopg2.connect(POSTGRES_URL)
        return conn
    except Exception as e:
        print(f"Postgres connection error: {e}")
        return None


# ------------------------------------------------------------
# Query Helper
# ------------------------------------------------------------
def query(sql: str, params=None):
    conn = get_connection()
    if not conn:
        return []

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params or ())
            results = cur.fetchall()
            conn.close()
            return results
    except Exception as e:
        print(f"Postgres query error: {e}")
        return []


# ------------------------------------------------------------
# Insert Helper
# ------------------------------------------------------------
def execute(sql: str, params=None):
    conn = get_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or ())
            conn.commit()
            conn.close()
            return True
    except Exception as e:
        print(f"Postgres execute error: {e}")
        return False
