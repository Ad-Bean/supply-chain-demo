-- ============================================================
-- Supply Chain Control Tower — Source Tables
-- RisingWave (PostgreSQL-compatible DDL)
-- ============================================================

-- Incoming customer orders
CREATE TABLE IF NOT EXISTS orders (
    order_id        VARCHAR PRIMARY KEY,
    customer_id     VARCHAR NOT NULL,
    customer_name   VARCHAR NOT NULL,
    product_id      VARCHAR NOT NULL,
    product_name    VARCHAR NOT NULL,
    quantity        INT     NOT NULL,
    warehouse_id    VARCHAR NOT NULL,
    priority        VARCHAR NOT NULL DEFAULT 'standard',  -- standard | express | vip
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Warehouse processing events (pick / pack / ship / delay)
CREATE TABLE IF NOT EXISTS warehouse_events (
    event_id        VARCHAR PRIMARY KEY,
    order_id        VARCHAR NOT NULL,
    warehouse_id    VARCHAR NOT NULL,
    event_type      VARCHAR NOT NULL,   -- received | picking | packed | shipped | delay
    delay_minutes   INT     NOT NULL DEFAULT 0,
    detail          VARCHAR,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Shipments linking orders to trucks
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id     VARCHAR PRIMARY KEY,
    order_id        VARCHAR NOT NULL,
    truck_id        VARCHAR NOT NULL,
    warehouse_id    VARCHAR NOT NULL,
    destination     VARCHAR NOT NULL,
    total_stops     INT     NOT NULL DEFAULT 1,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- GPS pings from delivery trucks
CREATE TABLE IF NOT EXISTS gps_pings (
    ping_id         VARCHAR PRIMARY KEY,
    truck_id        VARCHAR NOT NULL,
    lat             DOUBLE PRECISION NOT NULL,
    lon             DOUBLE PRECISION NOT NULL,
    speed_mph       DOUBLE PRECISION NOT NULL,
    heading         DOUBLE PRECISION NOT NULL,
    remaining_stops INT     NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Agent actions log (written by AI agents)
CREATE TABLE IF NOT EXISTS agent_actions (
    action_id       VARCHAR PRIMARY KEY,
    agent_name      VARCHAR NOT NULL,
    action_type     VARCHAR NOT NULL,   -- reroute | reassign | notify | escalate
    target_id       VARCHAR NOT NULL,   -- order_id, shipment_id, etc.
    reasoning       VARCHAR NOT NULL,
    detail          VARCHAR,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
