-- ============================================================
-- Supply Chain Control Tower — Materialized Views
-- These update continuously as new rows arrive.
-- ============================================================

-- MV1: Latest status per order (most recent warehouse event)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_order_status AS
SELECT DISTINCT ON (o.order_id)
    o.order_id,
    o.customer_id,
    o.customer_name,
    o.product_name,
    o.quantity,
    o.warehouse_id,
    o.priority,
    o.created_at        AS order_created,
    we.event_type       AS current_status,
    we.delay_minutes,
    we.created_at       AS status_updated_at
FROM orders o
LEFT JOIN warehouse_events we ON o.order_id = we.order_id
ORDER BY o.order_id, we.created_at DESC;

-- MV2: Inventory pressure per warehouse (orders in pipeline)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_warehouse_load AS
SELECT
    o.warehouse_id,
    COUNT(*)                                                    AS total_orders,
    COUNT(*) FILTER (WHERE we.event_type = 'received')          AS pending,
    COUNT(*) FILTER (WHERE we.event_type = 'picking')           AS picking,
    COUNT(*) FILTER (WHERE we.event_type = 'packed')            AS packed,
    COUNT(*) FILTER (WHERE we.event_type = 'shipped')           AS shipped,
    COUNT(*) FILTER (WHERE we.event_type = 'delay')             AS delayed,
    COALESCE(SUM(we.delay_minutes) FILTER (WHERE we.event_type = 'delay'), 0)
                                                                AS total_delay_min
FROM orders o
LEFT JOIN (
    SELECT DISTINCT ON (order_id) order_id, event_type, delay_minutes, created_at
    FROM warehouse_events
    ORDER BY order_id, created_at DESC
) we ON o.order_id = we.order_id
GROUP BY o.warehouse_id;

-- MV3: Shipment tracking — latest shipment per truck + latest GPS
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_shipment_tracking AS
SELECT
    s.shipment_id,
    s.order_id,
    s.truck_id,
    s.warehouse_id,
    s.destination,
    s.total_stops,
    gps.lat,
    gps.lon,
    gps.speed_mph,
    gps.remaining_stops,
    gps.created_at AS last_ping
FROM (
    SELECT DISTINCT ON (truck_id) *
    FROM shipments
    ORDER BY truck_id, created_at DESC
) s
LEFT JOIN (
    SELECT DISTINCT ON (truck_id) *
    FROM gps_pings
    ORDER BY truck_id, created_at DESC
) gps ON s.truck_id = gps.truck_id;

-- MV4: ETA predictions — simple model: remaining_stops * (avg segment time)
-- Compounding delay: if speed < 25 mph, add 15% per remaining stop
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_eta_predictions AS
SELECT
    s.shipment_id,
    s.order_id,
    s.truck_id,
    s.destination,
    gps.remaining_stops,
    gps.speed_mph,
    CASE
        WHEN gps.speed_mph > 0 THEN
            gps.remaining_stops * (10.0 / gps.speed_mph) * 60  -- base minutes per stop
            * CASE WHEN gps.speed_mph < 25 THEN POWER(1.15, gps.remaining_stops) ELSE 1.0 END
        WHEN gps.remaining_stops > 0 THEN
            gps.remaining_stops * 120.0  -- assume 2hr per stop when stopped
        ELSE NULL
    END AS eta_minutes,
    CASE
        WHEN gps.remaining_stops IS NULL OR gps.remaining_stops = 0 THEN 'delivered'
        WHEN gps.speed_mph >= 40 THEN 'on_time'
        WHEN gps.speed_mph >= 25 THEN 'slight_delay'
        ELSE 'delayed'
    END AS delay_status,
    CASE
        WHEN gps.remaining_stops IS NULL OR gps.remaining_stops = 0 THEN 1.0
        WHEN gps.speed_mph >= 40 THEN 0.92
        WHEN gps.speed_mph >= 25 THEN 0.75
        ELSE 0.55
    END AS confidence,
    gps.created_at AS computed_at
FROM (
    SELECT DISTINCT ON (truck_id) *
    FROM shipments
    ORDER BY truck_id, created_at DESC
) s
LEFT JOIN (
    SELECT DISTINCT ON (truck_id) *
    FROM gps_pings
    ORDER BY truck_id, created_at DESC
) gps ON s.truck_id = gps.truck_id;

-- MV5: Delay alerts — anything that needs attention
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_delay_alerts AS
SELECT
    'warehouse' AS alert_source,
    we.warehouse_id AS source_id,
    we.order_id AS affected_id,
    we.delay_minutes,
    we.detail AS reason,
    we.created_at
FROM (
    SELECT DISTINCT ON (order_id) *
    FROM warehouse_events
    WHERE event_type = 'delay' AND delay_minutes > 10
    ORDER BY order_id, created_at DESC
) we

UNION ALL

SELECT
    'shipment' AS alert_source,
    eta.truck_id AS source_id,
    eta.order_id AS affected_id,
    eta.eta_minutes::INT AS delay_minutes,
    CASE
        WHEN eta.speed_mph < 5  THEN 'Vehicle stopped — possible breakdown or accident'
        WHEN eta.speed_mph < 15 THEN 'Severe traffic congestion — speed ' || ROUND(eta.speed_mph::NUMERIC, 0) || 'mph'
        ELSE 'Traffic slowdown — speed ' || ROUND(eta.speed_mph::NUMERIC, 0) || 'mph'
    END AS reason,
    eta.computed_at AS created_at
FROM mv_eta_predictions eta
WHERE eta.delay_status = 'delayed';

-- MV6: Cascade impact — warehouse delay → which shipments & orders affected
-- Uses latest delay event per order to avoid duplicate rows
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_cascade_impact AS
SELECT
    we.warehouse_id,
    we.delay_minutes AS warehouse_delay_min,
    o.order_id,
    o.customer_name,
    o.priority,
    s.shipment_id,
    s.truck_id,
    s.destination
FROM (
    SELECT DISTINCT ON (order_id) order_id, warehouse_id, delay_minutes
    FROM warehouse_events
    WHERE event_type = 'delay' AND delay_minutes > 10
    ORDER BY order_id, created_at DESC
) we
JOIN orders o ON we.order_id = o.order_id
LEFT JOIN shipments s ON o.order_id = s.order_id;
