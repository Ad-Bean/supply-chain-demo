"""Database connection helper for RisingWave (PostgreSQL protocol)."""

import psycopg2
import psycopg2.extras

from config import RW


def get_conn():
    """Return a new connection to RisingWave."""
    return psycopg2.connect(**RW)


def execute(sql: str, params=None):
    """Execute a statement (INSERT / DDL) and commit."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()


def query(sql: str, params=None) -> list[dict]:
    """Run a SELECT and return rows as dicts."""
    with get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]


def query_one(sql: str, params=None) -> dict | None:
    """Run a SELECT and return the first row as a dict, or None."""
    rows = query(sql, params)
    return rows[0] if rows else None
