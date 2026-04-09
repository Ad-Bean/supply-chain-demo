"""Simulates GPS pings for trucks that have active shipments."""

import random
import time
import uuid

from db import execute, query
from config import GENERATOR_SPEED
from generators.seed_data import WAREHOUSES

# Rough starting coords per warehouse
WH_COORDS = {wh["id"]: (wh["lat"], wh["lon"]) for wh in WAREHOUSES}


def get_active_trucks() -> list[dict]:
    """Trucks with shipments that still have remaining stops > 0."""
    return query("""
        SELECT s.truck_id, s.warehouse_id, s.total_stops,
               COALESCE(gps.remaining_stops, s.total_stops) AS remaining_stops,
               COALESCE(gps.lat, 0) AS last_lat,
               COALESCE(gps.lon, 0) AS last_lon
        FROM (
            SELECT DISTINCT ON (truck_id) truck_id, warehouse_id, total_stops
            FROM shipments ORDER BY truck_id, created_at DESC
        ) s
        LEFT JOIN (
            SELECT DISTINCT ON (truck_id) truck_id, remaining_stops, lat, lon
            FROM gps_pings ORDER BY truck_id, created_at DESC
        ) gps ON s.truck_id = gps.truck_id
        WHERE COALESCE(gps.remaining_stops, s.total_stops) > 0
    """)


def emit_ping(truck: dict):
    wh_id = truck["warehouse_id"]
    base_lat, base_lon = WH_COORDS.get(wh_id, (40.0, -74.0))

    # Continue from last known position or start near warehouse
    lat = float(truck["last_lat"]) if truck["last_lat"] else base_lat
    lon = float(truck["last_lon"]) if truck["last_lon"] else base_lon

    if lat == 0 and lon == 0:
        lat, lon = base_lat, base_lon

    # Simulate movement
    lat += random.uniform(-0.005, 0.01)
    lon += random.uniform(-0.005, 0.01)

    remaining = max(0, int(truck["remaining_stops"]) - (1 if random.random() < 0.15 else 0))
    speed = random.uniform(5, 55) if remaining > 0 else 0
    heading = random.uniform(0, 360)

    execute(
        """INSERT INTO gps_pings (ping_id, truck_id, lat, lon, speed_mph,
           heading, remaining_stops)
           VALUES (%(pid)s, %(tid)s, %(lat)s, %(lon)s, %(spd)s, %(hdg)s, %(rem)s)""",
        {
            "pid": f"GPS-{uuid.uuid4().hex[:8].upper()}",
            "tid": truck["truck_id"],
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "spd": round(speed, 1),
            "hdg": round(heading, 1),
            "rem": remaining,
        },
    )
    print(f"[gps] {truck['truck_id']}  ({lat:.4f},{lon:.4f})  "
          f"{speed:.0f}mph  stops_left={remaining}")


def run(interval: float = 5.0, stop_event=None):
    while not (stop_event and stop_event.is_set()):
        trucks = get_active_trucks()
        for truck in trucks:
            if int(truck["remaining_stops"]) > 0:
                emit_ping(truck)
        time.sleep(interval / GENERATOR_SPEED)


if __name__ == "__main__":
    run()
