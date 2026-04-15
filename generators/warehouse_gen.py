"""Simulates warehouse processing: orders move through received → picking → packed → shipped.
Occasionally injects a delay event."""

import random
import time
import uuid

from db import execute, query
from config import GENERATOR_SPEED

# Normal processing pipeline
PIPELINE = ["received", "picking", "packed", "shipped"]

# Normal (non-disruption) delay reasons
NORMAL_DELAY_REASONS = [
    "Equipment malfunction — conveyor belt jam",
    "Scanner hardware failure — manual entry required",
    "Forklift battery died mid-aisle",
    "Mislabeled bin location — re-pick needed",
    "Quality check hold — damaged packaging detected",
    "Pallet wrapping machine offline",
    "Staff shift handover gap",
    "Barcode unreadable — manual verification",
    "Overweight package — repack required",
    "Dock door sensor fault — safety lockout",
]


def get_pending_orders() -> list[dict]:
    """Find orders whose latest event is not yet 'shipped'."""
    return query("""
        SELECT o.order_id, o.warehouse_id,
               COALESCE(
                   (SELECT we.event_type FROM warehouse_events we
                    WHERE we.order_id = o.order_id
                    ORDER BY we.created_at DESC LIMIT 1),
                   'new'
               ) AS current_status
        FROM orders o
        WHERE NOT EXISTS (
            SELECT 1 FROM warehouse_events we
            WHERE we.order_id = o.order_id AND we.event_type = 'shipped'
        )
        ORDER BY o.created_at
        LIMIT 50
    """)


def next_event_type(current: str) -> str | None:
    if current == "new":
        return "received"
    if current == "delay":
        return "received"  # re-enter pipeline after delay
    try:
        idx = PIPELINE.index(current)
        return PIPELINE[idx + 1] if idx + 1 < len(PIPELINE) else None
    except ValueError:
        return None


def insert_event(order_id: str, warehouse_id: str, event_type: str,
                 delay_minutes: int = 0, detail: str | None = None):
    execute(
        """INSERT INTO warehouse_events (event_id, order_id, warehouse_id,
           event_type, delay_minutes, detail)
           VALUES (%(eid)s, %(oid)s, %(wid)s, %(et)s, %(dm)s, %(d)s)""",
        {
            "eid": f"WE-{uuid.uuid4().hex[:8].upper()}",
            "oid": order_id,
            "wid": warehouse_id,
            "et": event_type,
            "dm": delay_minutes,
            "d": detail,
        },
    )


def run(interval: float = 3.0, stop_event=None, batch_size: int = 5):
    """Continuously advance orders through the warehouse pipeline."""
    # Process larger batches for the first few cycles to clear the seed backlog
    ramp_cycles = 6
    cycle = 0
    while not (stop_event and stop_event.is_set()):
        pending = get_pending_orders()
        if not pending:
            if stop_event:
                stop_event.wait(interval / GENERATOR_SPEED)
            else:
                time.sleep(interval / GENERATOR_SPEED)
            continue

        # During ramp-up, process more orders per cycle
        size = min(batch_size * 3, len(pending)) if cycle < ramp_cycles else min(batch_size, len(pending))
        cycle += 1
        batch = random.sample(pending, size)
        for order in batch:
            nxt = next_event_type(order["current_status"])
            if nxt is None:
                continue

            # 10% chance of a delay (only during picking or packing)
            if nxt in ("picking", "packed") and random.random() < 0.10:
                delay_min = random.choice([15, 30, 45, 60])
                reason = random.choice(NORMAL_DELAY_REASONS)
                insert_event(order["order_id"], order["warehouse_id"],
                             "delay", delay_min,
                             f"{reason} — {delay_min}min delay")
                print(f"[warehouse] DELAY {order['order_id']} @ {order['warehouse_id']} "
                      f"+{delay_min}min")
            else:
                insert_event(order["order_id"], order["warehouse_id"], nxt)
                print(f"[warehouse] {order['order_id']} → {nxt}")

        if stop_event:
            stop_event.wait(interval / GENERATOR_SPEED)
        else:
            time.sleep(interval / GENERATOR_SPEED)


if __name__ == "__main__":
    run()
