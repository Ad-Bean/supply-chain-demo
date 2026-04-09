"""Apply SQL schema to RisingWave — run once before starting generators."""

import re
from pathlib import Path

from db import get_conn

SQL_DIR = Path(__file__).parent.parent / "sql"


def run_sql_file(filepath: Path):
    print(f"Applying {filepath.name}...")
    raw = filepath.read_text()

    # Remove SQL comments
    raw = re.sub(r"--[^\n]*", "", raw)

    # Split on semicolons, skip empty
    stmts = [s.strip() for s in raw.split(";") if s.strip()]

    conn = get_conn()
    cur = conn.cursor()
    for stmt in stmts:
        try:
            print(f"  Executing: {stmt[:70]}...")
            cur.execute(stmt)
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"  Warning: {e}")
    cur.close()
    conn.close()
    print(f"  Done.")


def main():
    print("=== Setting up Supply Chain Control Tower schema ===\n")

    # Drop existing objects to start fresh
    conn = get_conn()
    cur = conn.cursor()
    for obj in [
        "DROP MATERIALIZED VIEW IF EXISTS mv_cascade_impact CASCADE",
        "DROP MATERIALIZED VIEW IF EXISTS mv_delay_alerts CASCADE",
        "DROP MATERIALIZED VIEW IF EXISTS mv_eta_predictions CASCADE",
        "DROP MATERIALIZED VIEW IF EXISTS mv_shipment_tracking CASCADE",
        "DROP MATERIALIZED VIEW IF EXISTS mv_warehouse_load CASCADE",
        "DROP MATERIALIZED VIEW IF EXISTS mv_order_status CASCADE",
        "DROP TABLE IF EXISTS agent_actions CASCADE",
        "DROP TABLE IF EXISTS gps_pings CASCADE",
        "DROP TABLE IF EXISTS shipments CASCADE",
        "DROP TABLE IF EXISTS warehouse_events CASCADE",
        "DROP TABLE IF EXISTS orders CASCADE",
    ]:
        try:
            cur.execute(obj)
            conn.commit()
        except Exception:
            conn.rollback()
    cur.close()
    conn.close()
    print("Dropped existing objects.\n")

    for f in sorted(SQL_DIR.glob("*.sql")):
        run_sql_file(f)
    print("\nSchema ready.")


if __name__ == "__main__":
    main()
