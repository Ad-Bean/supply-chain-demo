"""Generates a stream of customer orders into RisingWave."""

import random
import time
import uuid

from generators.seed_data import CUSTOMERS, PRODUCTS, WAREHOUSES
from db import execute
from config import GENERATOR_SPEED


def generate_order() -> dict:
    customer = random.choice(CUSTOMERS)
    product = random.choice(PRODUCTS)
    warehouse = random.choice(WAREHOUSES)
    order = {
        "order_id": f"ORD-{uuid.uuid4().hex[:8].upper()}",
        "customer_id": customer["id"],
        "customer_name": customer["name"],
        "product_id": product["id"],
        "product_name": product["name"],
        "quantity": random.randint(1, 5),
        "warehouse_id": warehouse["id"],
        "priority": customer["priority"],
    }
    return order


def insert_order(order: dict):
    execute(
        """INSERT INTO orders (order_id, customer_id, customer_name, product_id,
           product_name, quantity, warehouse_id, priority)
           VALUES (%(order_id)s, %(customer_id)s, %(customer_name)s, %(product_id)s,
           %(product_name)s, %(quantity)s, %(warehouse_id)s, %(priority)s)""",
        order,
    )


def run(count: int | None = None, interval: float = 2.0, stop_event=None):
    """Generate orders continuously or up to `count`."""
    i = 0
    while count is None or i < count:
        if stop_event and stop_event.is_set():
            break
        order = generate_order()
        insert_order(order)
        print(f"[order] {order['order_id']}  {order['customer_name']} → "
              f"{order['product_name']} @ {order['warehouse_id']}")
        i += 1
        time.sleep(interval / GENERATOR_SPEED)


if __name__ == "__main__":
    run()
