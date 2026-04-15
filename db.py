"""Database connection helper for RisingWave (PostgreSQL protocol).

Uses a connection pool to avoid the TCP+TLS handshake overhead of creating
a new connection for every query (~100-200ms per connect to a remote DB).
"""

import psycopg2
import psycopg2.extras
import psycopg2.pool
import threading

from config import RW

_pool: psycopg2.pool.ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """Lazily create a thread-safe connection pool (1-10 connections)."""
    global _pool
    if _pool is None or _pool.closed:
        with _pool_lock:
            if _pool is None or _pool.closed:
                _pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=1, maxconn=10, **RW,
                )
    return _pool


def get_conn():
    """Return a raw (non-pooled) connection.

    For callers that manage their own connection lifecycle (setup_schema, etc.)
    and call conn.close() directly. Internal db.py functions use the pool.
    """
    return psycopg2.connect(**RW)


def _putconn(conn):
    """Return a connection to the pool."""
    try:
        _get_pool().putconn(conn)
    except Exception:
        pass


def execute(sql: str, params=None):
    """Execute a statement (INSERT / DDL) and commit."""
    conn = _get_pool().getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
    finally:
        _putconn(conn)


def execute_batch(statements: list[tuple[str, tuple]]):
    """Execute multiple statements on a single connection and commit once."""
    conn = _get_pool().getconn()
    try:
        with conn.cursor() as cur:
            for sql, params in statements:
                cur.execute(sql, params)
        conn.commit()
    finally:
        _putconn(conn)


def query(sql: str, params=None) -> list[dict]:
    """Run a SELECT and return rows as dicts."""
    conn = _get_pool().getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]
    finally:
        _putconn(conn)


def query_batch(queries: dict[str, str]) -> dict[str, list[dict]]:
    """Run multiple SELECTs on a single connection. Returns {key: rows}."""
    conn = _get_pool().getconn()
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
        _putconn(conn)
