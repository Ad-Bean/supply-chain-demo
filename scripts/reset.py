"""Reset all data for a fresh demo run. Keeps schema intact."""

from db import get_conn


def main():
    tables = ["agent_actions", "gps_pings", "shipments", "warehouse_events", "orders"]
    conn = get_conn()
    cur = conn.cursor()
    for t in tables:
        cur.execute(f"DELETE FROM {t}")
        print(f"  Cleared {t}")
    conn.commit()
    cur.close()
    conn.close()
    print("\nAll data cleared. Ready for a fresh demo run.")


if __name__ == "__main__":
    main()
