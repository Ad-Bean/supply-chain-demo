"""Run all data generators concurrently in threads."""

import threading
import time

from generators.order_gen import run as run_orders
from generators.warehouse_gen import run as run_warehouse
from generators.shipment_gen import run as run_shipments
from generators.gps_gen import run as run_gps


def main():
    print("=== Starting Supply Chain Data Generators ===\n")
    print("  [1] Order generator       (every ~2s)")
    print("  [2] Warehouse processor   (every ~3s)")
    print("  [3] Shipment creator      (every ~2s)")
    print("  [4] GPS ping emitter      (every ~5s)")
    print()

    threads = [
        threading.Thread(target=run_orders,    kwargs={"interval": 2.0}, daemon=True),
        threading.Thread(target=run_warehouse, kwargs={"interval": 3.0}, daemon=True),
        threading.Thread(target=run_shipments, kwargs={"interval": 2.0}, daemon=True),
        threading.Thread(target=run_gps,       kwargs={"interval": 5.0}, daemon=True),
    ]

    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nGenerators stopped.")


if __name__ == "__main__":
    main()
