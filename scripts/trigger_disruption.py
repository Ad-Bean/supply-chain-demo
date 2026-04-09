"""Manually trigger a warehouse disruption — the demo's "wow moment" button.

Usage:
    python scripts/trigger_disruption.py                 # random warehouse, 45-min delay
    python scripts/trigger_disruption.py WH-03 60        # specific warehouse, 60-min delay
"""

import sys
import uuid
import random

from db import execute, query

from generators.seed_data import WAREHOUSES


def trigger(warehouse_id: str | None = None, delay_minutes: int = 45,
            detail: str | None = None) -> int:
    """Inject delay events. Returns number of affected orders."""
    if warehouse_id is None:
        warehouse_id = random.choice(WAREHOUSES)["id"]
    if detail is None:
        detail = f"MAJOR DISRUPTION: Equipment failure — all operations halted for {delay_minutes}min"

    pending = query("""
        SELECT DISTINCT o.order_id, o.customer_name, o.priority
        FROM orders o
        LEFT JOIN (
            SELECT DISTINCT ON (order_id) order_id, event_type
            FROM warehouse_events
            ORDER BY order_id, created_at DESC
        ) we ON o.order_id = we.order_id
        WHERE o.warehouse_id = %s
          AND COALESCE(we.event_type, 'new') NOT IN ('shipped')
    """, (warehouse_id,))

    if not pending:
        print(f"No pending orders at {warehouse_id}. Generate some orders first.")
        return 0

    print(f"\n{'='*60}")
    print(f"  DISRUPTION TRIGGERED @ {warehouse_id}")
    print(f"  Delay: {delay_minutes} minutes")
    print(f"  Affected orders: {len(pending)}")
    print(f"{'='*60}\n")

    for order in pending:
        event_id = f"WE-{uuid.uuid4().hex[:8].upper()}"
        execute(
            """INSERT INTO warehouse_events (event_id, order_id, warehouse_id,
               event_type, delay_minutes, detail)
               VALUES (%s, %s, %s, 'delay', %s, %s)""",
            (event_id, order["order_id"], warehouse_id, delay_minutes, detail),
        )
        print(f"  {order['order_id']}  {order['customer_name']:20s}  "
              f"priority={order['priority']}")

    print(f"\n  {len(pending)} delay events injected.\n")
    return len(pending)


if __name__ == "__main__":
    wh = sys.argv[1] if len(sys.argv) > 1 else None
    mins = int(sys.argv[2]) if len(sys.argv) > 2 else 45
    trigger(wh, mins)
