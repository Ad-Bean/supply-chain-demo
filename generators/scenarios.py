"""Predefined real-world disruption scenarios for the supply chain demo."""

import random

SCENARIOS = [
    {
        "id": "equipment_failure",
        "name": "Equipment Failure",
        "icon": "🔧",
        "description": "Conveyor belt malfunction halts picking line at {warehouse}",
        "detail": "EQUIPMENT FAILURE: Main conveyor belt seized — picking line halted, "
                  "maintenance ETA {delay}min. All in-progress orders delayed.",
        "warehouses": ["WH-01", "WH-02", "WH-03"],
        "delay_range": (30, 60),
    },
    {
        "id": "power_outage",
        "name": "Power Outage",
        "icon": "⚡",
        "description": "Power grid failure knocks out {warehouse} operations",
        "detail": "POWER OUTAGE: Grid failure at facility. Backup generators covering "
                  "cold storage only. All picking/packing suspended for {delay}min.",
        "warehouses": ["WH-01", "WH-02", "WH-03"],
        "delay_range": (45, 90),
    },
    {
        "id": "labor_shortage",
        "name": "Labor Shortage",
        "icon": "👷",
        "description": "Staff call-outs reduce {warehouse} capacity by 60%",
        "detail": "LABOR SHORTAGE: 60% of shift called out (flu outbreak). "
                  "Operating at minimal capacity. Processing delayed {delay}min per order.",
        "warehouses": ["WH-01", "WH-02", "WH-03"],
        "delay_range": (20, 45),
    },
    {
        "id": "inventory_miscount",
        "name": "Inventory Miscount",
        "icon": "📦",
        "description": "Cycle count discrepancy triggers audit at {warehouse}",
        "detail": "INVENTORY AUDIT: Cycle count found 15% discrepancy in Zone B. "
                  "Emergency audit in progress — affected aisles locked for {delay}min.",
        "warehouses": ["WH-02", "WH-03"],
        "delay_range": (25, 50),
    },
    {
        "id": "severe_weather",
        "name": "Severe Weather",
        "icon": "🌪️",
        "description": "Tornado warning forces shelter-in-place at {warehouse}",
        "detail": "SEVERE WEATHER: Tornado warning issued for facility area. "
                  "All personnel sheltering in place. Operations suspended {delay}min.",
        "warehouses": ["WH-01", "WH-02"],
        "delay_range": (30, 75),
    },
    {
        "id": "system_outage",
        "name": "WMS System Outage",
        "icon": "💻",
        "description": "Warehouse Management System crash at {warehouse}",
        "detail": "SYSTEM OUTAGE: WMS database unresponsive. Cannot confirm picks or "
                  "generate shipping labels. IT restoring from backup — ETA {delay}min.",
        "warehouses": ["WH-01", "WH-02", "WH-03"],
        "delay_range": (20, 40),
    },
    {
        "id": "fire_alarm",
        "name": "Fire Alarm Evacuation",
        "icon": "🚨",
        "description": "Fire alarm triggers mandatory evacuation at {warehouse}",
        "detail": "FIRE ALARM: Smoke detected in loading dock area. Full evacuation "
                  "initiated. Fire department on scene. Reentry ETA {delay}min.",
        "warehouses": ["WH-01", "WH-03"],
        "delay_range": (40, 90),
    },
    {
        "id": "shipping_backup",
        "name": "Shipping Dock Backup",
        "icon": "🚛",
        "description": "Truck scheduling error creates dock congestion at {warehouse}",
        "detail": "DOCK BACKUP: 8 trucks arrived simultaneously due to scheduling error. "
                  "Only 3 loading bays available. Outbound shipments delayed {delay}min.",
        "warehouses": ["WH-02", "WH-03"],
        "delay_range": (25, 55),
    },
]


def pick_random_scenario() -> dict:
    """Pick a random scenario with a random warehouse and delay."""
    scenario = random.choice(SCENARIOS)
    warehouse = random.choice(scenario["warehouses"])
    delay = random.randint(*scenario["delay_range"])
    return {
        **scenario,
        "warehouse": warehouse,
        "delay": delay,
        "description": scenario["description"].format(warehouse=warehouse),
        "detail": scenario["detail"].format(warehouse=warehouse, delay=delay),
    }


def resolve_scenario(scenario_id: str, warehouse: str | None = None) -> dict:
    """Resolve a scenario by ID with optional warehouse override."""
    scenario = next(s for s in SCENARIOS if s["id"] == scenario_id)
    wh = warehouse or random.choice(scenario["warehouses"])
    delay = random.randint(*scenario["delay_range"])
    return {
        **scenario,
        "warehouse": wh,
        "delay": delay,
        "description": scenario["description"].format(warehouse=wh),
        "detail": scenario["detail"].format(warehouse=wh, delay=delay),
    }
