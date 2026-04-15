"""Creates shipments when orders reach 'shipped' status and assigns trucks."""

import random
import time
import uuid

from db import execute, query
from config import GENERATOR_SPEED
from generators.seed_data import DESTINATIONS, TRUCKS


def get_shipped_without_shipment() -> list[dict]:
    """Orders that have been shipped but don't have a shipment record yet."""
    return query("""
        SELECT DISTINCT o.order_id, o.warehouse_id
        FROM orders o
        JOIN warehouse_events we ON o.order_id = we.order_id
        LEFT JOIN shipments s ON o.order_id = s.order_id
        WHERE we.event_type = 'shipped'
          AND s.shipment_id IS NULL
    """)


def create_shipment(order_id: str, warehouse_id: str):
    # Pick a truck from the same warehouse
    wh_trucks = [t for t in TRUCKS if t["warehouse_id"] == warehouse_id]
    truck = random.choice(wh_trucks) if wh_trucks else random.choice(TRUCKS)
    dest = random.choice(DESTINATIONS)
    total_stops = random.randint(3, 12)

    shipment = {
        "sid": f"SHP-{uuid.uuid4().hex[:8].upper()}",
        "oid": order_id,
        "tid": truck["id"],
        "wid": warehouse_id,
        "dest": dest,
        "stops": total_stops,
    }
    execute(
        """INSERT INTO shipments (shipment_id, order_id, truck_id, warehouse_id,
           destination, total_stops)
           VALUES (%(sid)s, %(oid)s, %(tid)s, %(wid)s, %(dest)s, %(stops)s)""",
        shipment,
    )
    print(f"[shipment] {shipment['sid']}  {order_id} → {truck['id']} → {dest} "
          f"({total_stops} stops)")


def run(interval: float = 2.0, stop_event=None):
    while not (stop_event and stop_event.is_set()):
        ready = get_shipped_without_shipment()
        for order in ready:
            create_shipment(order["order_id"], order["warehouse_id"])
        if stop_event:
            stop_event.wait(interval / GENERATOR_SPEED)
        else:
            time.sleep(interval / GENERATOR_SPEED)


if __name__ == "__main__":
    run()
