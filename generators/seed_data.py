"""Seed data constants for the supply chain demo."""

WAREHOUSES = [
    {"id": "WH-01", "name": "East Coast Hub",    "city": "Newark, NJ",      "lat": 40.7357, "lon": -74.1724},
    {"id": "WH-02", "name": "Midwest Center",    "city": "Columbus, OH",    "lat": 39.9612, "lon": -82.9988},
    {"id": "WH-03", "name": "West Coast Depot",  "city": "Ontario, CA",     "lat": 34.0633, "lon": -117.6509},
]

PRODUCTS = [
    {"id": "PRD-001", "name": "Wireless Earbuds"},
    {"id": "PRD-002", "name": "Smart Watch"},
    {"id": "PRD-003", "name": "Laptop Stand"},
    {"id": "PRD-004", "name": "USB-C Hub"},
    {"id": "PRD-005", "name": "Mechanical Keyboard"},
    {"id": "PRD-006", "name": "4K Webcam"},
    {"id": "PRD-007", "name": "Portable SSD 2TB"},
    {"id": "PRD-008", "name": "Noise-Canceling Headphones"},
]

CUSTOMERS = [
    {"id": "CUST-001", "name": "Alice Chen",      "priority": "vip"},
    {"id": "CUST-002", "name": "Bob Martinez",    "priority": "standard"},
    {"id": "CUST-003", "name": "Carol Wu",         "priority": "express"},
    {"id": "CUST-004", "name": "David Kim",       "priority": "standard"},
    {"id": "CUST-005", "name": "Eva Johansson",   "priority": "vip"},
    {"id": "CUST-006", "name": "Frank Osei",      "priority": "standard"},
    {"id": "CUST-007", "name": "Grace Patel",     "priority": "express"},
    {"id": "CUST-008", "name": "Hiro Tanaka",     "priority": "standard"},
]

DESTINATIONS = [
    "Brooklyn, NY", "Manhattan, NY", "Philadelphia, PA", "Boston, MA",
    "Chicago, IL", "Detroit, MI", "Indianapolis, IN", "Cincinnati, OH",
    "Los Angeles, CA", "San Diego, CA", "Phoenix, AZ", "Las Vegas, NV",
]

TRUCKS = [
    {"id": f"TRUCK-{i:02d}", "warehouse_id": WAREHOUSES[i % len(WAREHOUSES)]["id"]}
    for i in range(1, 21)
]
