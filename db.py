"""Database connection helper for RisingWave (PostgreSQL protocol)."""

import psycopg2
import psycopg2.extras

from config import RW


def get_conn():
    """Return a new connection to RisingWave."""
    return psycopg2.connect(**RW)


def execute(sql: str, params=None):
    """Execute a statement (INSERT / DDL) and commit."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def execute_batch(statements: list[tuple[str, tuple]]):
    """Execute multiple statements on a single connection and commit once."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            for sql, params in statements:
                cur.execute(sql, params)
        conn.commit()
    finally:
        conn.close()


def query(sql: str, params=None) -> list[dict]:
    """Run a SELECT and return rows as dicts."""
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def query_batch(queries: dict[str, str]) -> dict[str, list[dict]]:
    """Run multiple SELECTs on a single connection. Returns {key: rows}."""
    conn = get_conn()
    try:
        results = {}
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for key, sql in queries.items():
                try:
                    cur.execute(sql)
                    results[key] = [dict(r) for r in cur.fetchall()]
                except Exception:
                    conn.rollback()
                    results[key] = []
        return results
    finally:
        conn.close()
