"""Materialized view SQL definitions shown when 'Show SQL' is enabled."""

import streamlit as st

MV_SQL = {
    "order_status": {
        "name": "mv_order_status",
        "explain": "Joins `orders` with `warehouse_events` to find each order's latest status. "
                   "RisingWave keeps this **incrementally updated** — every new event instantly "
                   "refreshes the view without re-scanning the full table.",
        "sql": """\
CREATE MATERIALIZED VIEW mv_order_status AS
SELECT DISTINCT ON (o.order_id)
    o.order_id, o.customer_id, o.customer_name, o.product_name,
    o.quantity, o.warehouse_id, o.priority,
    o.created_at AS order_created,
    we.event_type AS current_status, we.delay_minutes,
    we.created_at AS status_updated_at
FROM orders o
LEFT JOIN warehouse_events we ON o.order_id = we.order_id
ORDER BY o.order_id, we.created_at DESC;""",
    },
    "warehouse_load": {
        "name": "mv_warehouse_load",
        "explain": "Aggregates order counts per warehouse per stage using `FILTER (WHERE ...)`. "
                   "This is a **streaming GROUP BY** — RisingWave maintains the counts incrementally "
                   "as events arrive, not by re-aggregating all rows.",
        "sql": """\
CREATE MATERIALIZED VIEW mv_warehouse_load AS
SELECT
    o.warehouse_id,
    COUNT(*) AS total_orders,
    COUNT(*) FILTER (WHERE we.event_type = 'received') AS pending,
    COUNT(*) FILTER (WHERE we.event_type = 'picking')  AS picking,
    COUNT(*) FILTER (WHERE we.event_type = 'packed')   AS packed,
    COUNT(*) FILTER (WHERE we.event_type = 'shipped')  AS shipped,
    COUNT(*) FILTER (WHERE we.event_type = 'delay')    AS delayed,
    COALESCE(SUM(we.delay_minutes)
        FILTER (WHERE we.event_type = 'delay'), 0)     AS total_delay_min
FROM orders o
LEFT JOIN (...latest event per order...) we ON o.order_id = we.order_id
GROUP BY o.warehouse_id;""",
    },
    "eta": {
        "name": "mv_eta_predictions",
        "explain": "Computes ETAs from live GPS speed and remaining stops. Uses a **compounding "
                   "delay factor** — if speed drops below 25 mph, each remaining stop adds 15% more "
                   "delay. Stopped trucks (0 mph) get a fallback ETA of 2 hours per remaining stop. "
                   "Confidence scores reflect speed thresholds. All in streaming SQL.",
        "sql": """\
CREATE MATERIALIZED VIEW mv_eta_predictions AS
SELECT
    s.shipment_id, s.truck_id, s.destination,
    gps.remaining_stops, gps.speed_mph,
    CASE WHEN gps.speed_mph > 0 THEN
        gps.remaining_stops * (10.0 / gps.speed_mph) * 60
        * CASE WHEN gps.speed_mph < 25
               THEN POWER(1.15, gps.remaining_stops)
               ELSE 1.0 END
    WHEN gps.remaining_stops > 0 THEN
        gps.remaining_stops * 120.0  -- fallback for stopped trucks
    ELSE NULL END AS eta_minutes,
    CASE WHEN remaining_stops = 0 THEN 'delivered'
         WHEN gps.speed_mph >= 40 THEN 'on_time'
         WHEN gps.speed_mph >= 25 THEN 'slight_delay'
         ELSE 'delayed' END AS delay_status,
    CASE WHEN remaining_stops = 0 THEN 1.0
         WHEN gps.speed_mph >= 40 THEN 0.92
         WHEN gps.speed_mph >= 25 THEN 0.75
         ELSE 0.55 END AS confidence
FROM (...latest shipment per truck...) s
LEFT JOIN (...latest GPS per truck...) gps ON s.truck_id = gps.truck_id;""",
    },
    "alerts": {
        "name": "mv_delay_alerts",
        "explain": "Combines two alert sources with `UNION ALL`: warehouse delays >10 min "
                   "and shipments flagged as delayed by the ETA view. This MV **chains off another "
                   "MV** (`mv_eta_predictions`) — RisingWave propagates changes through the DAG "
                   "automatically. A GPS ping drop cascades into an alert with zero application code.",
        "sql": """\
CREATE MATERIALIZED VIEW mv_delay_alerts AS
-- Source 1: Warehouse delays
SELECT 'warehouse' AS alert_source, we.warehouse_id AS source_id,
       we.order_id AS affected_id, we.delay_minutes,
       we.detail AS reason, we.created_at
FROM warehouse_events we
WHERE we.event_type = 'delay' AND we.delay_minutes > 10
UNION ALL
-- Source 2: Shipment delays (chained from mv_eta_predictions)
SELECT 'shipment', eta.truck_id, eta.order_id,
       eta.eta_minutes::INT,
       CASE WHEN eta.speed_mph < 5
            THEN 'Vehicle stopped — possible breakdown'
            WHEN eta.speed_mph < 15
            THEN 'Severe traffic congestion'
            ELSE 'Traffic slowdown' END,
       eta.computed_at
FROM mv_eta_predictions eta
WHERE eta.delay_status = 'delayed';""",
    },
    "actions": {
        "name": "agent_actions (table)",
        "explain": "This is a regular table, not a materialized view. AI agents write their "
                   "decisions here (reroutes, resolutions, notifications, escalations). The "
                   "dashboard reads it like any other table — RisingWave serves it via the "
                   "PostgreSQL protocol.",
        "sql": """\
CREATE TABLE agent_actions (
    action_id   VARCHAR PRIMARY KEY,
    agent_name  VARCHAR NOT NULL,
    action_type VARCHAR NOT NULL,  -- reroute | resolve | notify | escalate
    target_id   VARCHAR NOT NULL,
    reasoning   VARCHAR NOT NULL,
    detail      VARCHAR,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);""",
    },
    "cascade": {
        "name": "mv_cascade_impact",
        "explain": "A **multi-way streaming JOIN** across `warehouse_events`, `orders`, and "
                   "`shipments`. When a delay hits one warehouse, this view instantly shows "
                   "every affected customer, shipment, and truck — the full blast radius. "
                   "No batch job, no ETL pipeline.",
        "sql": """\
CREATE MATERIALIZED VIEW mv_cascade_impact AS
SELECT
    we.warehouse_id, we.delay_minutes AS warehouse_delay_min,
    o.order_id, o.customer_name, o.priority,
    s.shipment_id, s.truck_id, s.destination
FROM warehouse_events we
JOIN orders o ON we.order_id = o.order_id
LEFT JOIN shipments s ON o.order_id = s.order_id
WHERE we.event_type = 'delay' AND we.delay_minutes > 10;""",
    },
    "fleet_map": {
        "name": "mv_shipment_tracking",
        "explain": "Joins the latest shipment per truck with the latest GPS ping to show "
                   "real-time position, speed, and remaining stops. Both sides use "
                   "`DISTINCT ON (truck_id)` so each truck appears exactly once. "
                   "RisingWave maintains this join incrementally as new pings arrive.",
        "sql": """\
CREATE MATERIALIZED VIEW mv_shipment_tracking AS
SELECT
    s.shipment_id, s.order_id, s.truck_id,
    s.warehouse_id, s.destination, s.total_stops,
    gps.lat, gps.lon, gps.speed_mph, gps.remaining_stops,
    gps.created_at AS last_ping
FROM (
    SELECT DISTINCT ON (truck_id) *
    FROM shipments ORDER BY truck_id, created_at DESC
) s
LEFT JOIN (
    SELECT DISTINCT ON (truck_id) *
    FROM gps_pings ORDER BY truck_id, created_at DESC
) gps ON s.truck_id = gps.truck_id;""",
    },
}


def show_sql(section_key: str):
    """Render the SQL expander for a section if Show SQL is enabled."""
    if not st.session_state.get("show_sql"):
        return
    mv = MV_SQL.get(section_key)
    if not mv:
        return
    with st.expander(f"**{mv['name']}** — How this works in RisingWave", expanded=False):
        st.markdown(mv["explain"])
        st.code(mv["sql"], language="sql")
