"""Materialized view SQL definitions for the dashboard."""

MV_SQL = {
    "order_status": {
        "name": "mv_order_status",
        "explain": "Joins `orders` with `warehouse_events` to find each order's latest status. "
                   "RisingWave keeps this **incrementally updated**, every new event instantly "
                   "refreshes the view without re-scanning the full table.",
        "sql": """\
CREATE MATERIALIZED VIEW mv_order_status AS
SELECT DISTINCT ON (o.order_id)
    o.order_id, o.customer_name, o.priority, o.warehouse_id,
    we.event_type AS current_status, we.delay_minutes
FROM orders o
LEFT JOIN warehouse_events we ON o.order_id = we.order_id
ORDER BY o.order_id, we.created_at DESC;""",
    },
    "warehouse_load": {
        "name": "mv_warehouse_load",
        "explain": "Aggregates order counts per warehouse per stage using `FILTER (WHERE ...)`. "
                   "This is a **streaming GROUP BY**, RisingWave maintains the counts incrementally "
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
    COUNT(*) FILTER (WHERE we.event_type = 'delay')    AS delayed
FROM orders o
LEFT JOIN (...latest event per order...) we ON o.order_id = we.order_id
GROUP BY o.warehouse_id;""",
    },
    "eta": {
        "name": "mv_eta_predictions",
        "explain": "Computes ETAs from live GPS speed and remaining stops. Uses a **compounding "
                   "delay factor**, if speed drops below 25 mph, each remaining stop adds 15% more "
                   "delay. Confidence scores are derived from speed thresholds. All computed in "
                   "streaming SQL, no application code needed.",
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
    ELSE NULL END AS eta_minutes,
    CASE WHEN gps.speed_mph >= 40 THEN 'on_time'
         WHEN gps.speed_mph >= 25 THEN 'slight_delay'
         ELSE 'delayed' END AS delay_status
FROM shipments s
LEFT JOIN (...latest GPS per truck...) gps ON s.truck_id = gps.truck_id;""",
    },
    "alerts": {
        "name": "mv_delay_alerts",
        "explain": "Combines two alert sources with `UNION ALL`: warehouse delays >10 min "
                   "and shipments flagged as delayed by the ETA view. This MV **chains off another "
                   "MV** (`mv_eta_predictions`), RisingWave propagates changes through the DAG automatically.",
        "sql": """\
CREATE MATERIALIZED VIEW mv_delay_alerts AS
SELECT 'warehouse' AS alert_source, we.warehouse_id AS source_id,
       we.order_id AS affected_id, we.delay_minutes, we.detail AS reason
FROM warehouse_events we
WHERE we.event_type = 'delay' AND we.delay_minutes > 10
UNION ALL
SELECT 'shipment', eta.truck_id, eta.order_id,
       eta.eta_minutes::INT, eta.delay_status
FROM mv_eta_predictions eta
WHERE eta.delay_status = 'delayed';""",
    },
    "actions": {
        "name": "agent_actions (table)",
        "explain": "This is a regular table, not a materialized view. AI agents write their "
                   "decisions here (reroutes, notifications, escalations). The dashboard reads "
                   "it like any other table, RisingWave serves it via the PostgreSQL protocol.",
        "sql": """\
CREATE TABLE agent_actions (
    action_id   VARCHAR PRIMARY KEY,
    agent_name  VARCHAR NOT NULL,
    action_type VARCHAR NOT NULL,  -- reroute | notify | escalate
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
                   "every affected customer, shipment, and truck, the full blast radius. "
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
        "explain": "Joins `shipments` with the latest GPS ping per truck to show real-time "
                   "position, speed, and remaining stops. RisingWave maintains this join "
                   "incrementally as new GPS pings arrive every few seconds.",
        "sql": """\
CREATE MATERIALIZED VIEW mv_shipment_tracking AS
SELECT
    s.shipment_id, s.order_id, s.truck_id,
    s.warehouse_id, s.destination, s.total_stops,
    gps.lat, gps.lon, gps.speed_mph, gps.remaining_stops,
    gps.created_at AS last_ping
FROM shipments s
LEFT JOIN (
    SELECT DISTINCT ON (truck_id) *
    FROM gps_pings ORDER BY truck_id, created_at DESC
) gps ON s.truck_id = gps.truck_id;""",
    },
}
