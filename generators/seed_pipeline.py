"""Seed the full pipeline with data at every stage.

Uses batch inserts (single connection) for fast seeding so every
dashboard panel has data immediately when generators start.
"""

import random
import uuid

from db import get_conn, query
from generators.seed_data import CUSTOMERS, PRODUCTS, WAREHOUSES, DESTINATIONS, TRUCKS

WH_COORDS = {wh["id"]: (wh["lat"], wh["lon"]) for wh in WAREHOUSES}


def _uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def seed(n_orders: int = 20):
    """Seed n_orders across all pipeline stages + shipments + GPS.

    Skips seeding if orders already exist (prevents duplicates on
    page refresh or toggle off/on).
    """
    existing = query("SELECT COUNT(*) as c FROM orders")
    if existing and existing[0]["c"] > 0:
        print(f"[seed] Skipped — {existing[0]['c']} orders already exist")
        return

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            orders = []
            for _ in range(n_orders):
                customer = random.choice(CUSTOMERS)
                product = random.choice(PRODUCTS)
                warehouse = random.choice(WAREHOUSES)
                orders.append({
                    "order_id": _uid("ORD"),
                    "customer_id": customer["id"],
                    "customer_name": customer["name"],
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "quantity": random.randint(1, 5),
                    "warehouse_id": warehouse["id"],
                    "priority": customer["priority"],
                })

            # Assign stages
            stage_splits = [
                (0.15, ["received"]),
                (0.15, ["received", "picking"]),
                (0.20, ["received", "picking", "packed"]),
                (0.50, ["received", "picking", "packed", "shipped"]),
            ]

            idx = 0
            shipped_orders = []
            for frac, stages in stage_splits:
                count = max(1, int(n_orders * frac))
                for _ in range(count):
                    if idx >= len(orders):
                        break
                    order = orders[idx]
                    idx += 1

                    cur.execute(
                        """INSERT INTO orders (order_id, customer_id, customer_name, product_id,
                           product_name, quantity, warehouse_id, priority)
                           VALUES (%(order_id)s, %(customer_id)s, %(customer_name)s, %(product_id)s,
                           %(product_name)s, %(quantity)s, %(warehouse_id)s, %(priority)s)""",
                        order,
                    )

                    for stage in stages:
                        cur.execute(
                            """INSERT INTO warehouse_events (event_id, order_id, warehouse_id,
                               event_type, delay_minutes, detail)
                               VALUES (%s, %s, %s, %s, 0, NULL)""",
                            (_uid("WE"), order["order_id"], order["warehouse_id"], stage),
                        )

                    if stages[-1] == "shipped":
                        shipped_orders.append(order)

            # Create shipments and GPS for shipped orders
            trucks_used = set()
            for order in shipped_orders:
                wh_trucks = [t for t in TRUCKS if t["warehouse_id"] == order["warehouse_id"]
                             and t["id"] not in trucks_used]
                if not wh_trucks:
                    wh_trucks = [t for t in TRUCKS if t["id"] not in trucks_used]
                if not wh_trucks:
                    continue

                truck = random.choice(wh_trucks)
                trucks_used.add(truck["id"])
                dest = random.choice(DESTINATIONS)
                total_stops = random.randint(4, 10)
                remaining = random.randint(2, total_stops - 1)

                cur.execute(
                    """INSERT INTO shipments (shipment_id, order_id, truck_id, warehouse_id,
                       destination, total_stops)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (_uid("SHP"), order["order_id"], truck["id"],
                     order["warehouse_id"], dest, total_stops),
                )

                base_lat, base_lon = WH_COORDS[order["warehouse_id"]]
                lat = base_lat + random.uniform(-0.1, 0.2)
                lon = base_lon + random.uniform(-0.1, 0.2)
                speed = random.uniform(40, 60)

                cur.execute(
                    """INSERT INTO gps_pings (ping_id, truck_id, lat, lon, speed_mph,
                       heading, remaining_stops)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (_uid("GPS"), truck["id"], round(lat, 6), round(lon, 6),
                     round(speed, 1), round(random.uniform(0, 360), 1), remaining),
                )

        conn.commit()
        print(f"[seed] Seeded {len(orders)} orders, "
              f"{len(shipped_orders)} shipments, "
              f"{len(trucks_used)} trucks on map")
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
