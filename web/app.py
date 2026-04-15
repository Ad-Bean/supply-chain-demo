"""Supply Chain Control Tower — Live Streaming Dashboard (Streamlit)"""

import threading
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import query_batch, warmup

# Pre-warm the connection pool on first load so toggle clicks don't
# pay the TCP+TLS handshake cost (~200-500ms to RisingWave Cloud).
warmup()
from web.theme import (
    RW_ICON, RW_LOGO, RW_URL, RW_DOCS, RW_GITHUB, RW_CLOUD,
    BRAND_BLUE_LIGHT, BRAND_GREEN, TEXT_MUTED, TEXT_DIM, ERROR,
    inject_css,
)
from web.panels import (
    render_pipeline, render_kpi, render_order_funnel, render_warehouse_load,
    render_fleet_map, render_eta, render_alerts,
    render_agent_actions, render_cascade, render_section_header,
)

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="RisingWave | AI-Native Supply Chain",
    page_icon=RW_ICON,
    layout="wide",
)
inject_css()

# ── Background services ──────────────────────────────────────────────────────

if "gen_stop" not in st.session_state:
    st.session_state.gen_stop = threading.Event()
if "agent_stop" not in st.session_state:
    st.session_state.agent_stop = threading.Event()

# Process-level stop events — shared across all sessions so new sessions
# can stop orphan threads from expired sessions.
_GLOBAL_GEN_STOP: threading.Event | None = None
_GLOBAL_AGENT_STOP: threading.Event | None = None


def _start_threads(stop_key, thread_configs):
    global _GLOBAL_GEN_STOP, _GLOBAL_AGENT_STOP

    # Stop any orphan threads from previous sessions
    if stop_key == "gen_stop" and _GLOBAL_GEN_STOP is not None:
        _GLOBAL_GEN_STOP.set()
    if stop_key == "agent_stop" and _GLOBAL_AGENT_STOP is not None:
        _GLOBAL_AGENT_STOP.set()

    st.session_state[stop_key] = threading.Event()
    stop = st.session_state[stop_key]

    # Track at process level
    if stop_key == "gen_stop":
        _GLOBAL_GEN_STOP = stop
    else:
        _GLOBAL_AGENT_STOP = stop

    for target, kwargs in thread_configs:
        kwargs["stop_event"] = stop
        threading.Thread(target=target, kwargs=kwargs, daemon=True).start()


def _on_gen_toggle():
    if st.session_state.gen_toggle:
        from generators.seed_pipeline import seed
        from generators.order_gen import run as run_orders
        from generators.warehouse_gen import run as run_warehouse
        from generators.shipment_gen import run as run_shipments
        from generators.gps_gen import run as run_gps
        # Seed the pipeline so every panel has data immediately
        seed(n_orders=20)
        _start_threads("gen_stop", [
            (run_orders, {"interval": 4.0}),
            (run_warehouse, {"interval": 2.0, "batch_size": 5}),
            (run_shipments, {"interval": 2.0}),
            (run_gps, {"interval": 3.0}),
        ])
        # Auto-start AI agents so the demo is one-click
        if not st.session_state.get("agent_toggle"):
            st.session_state.agent_toggle = True
            _on_agent_toggle()
    else:
        st.session_state.gen_stop.set()
        # Stop agents when generators stop
        if st.session_state.get("agent_toggle"):
            st.session_state.agent_toggle = False
            st.session_state.agent_stop.set()


def _on_agent_toggle():
    if st.session_state.agent_toggle:
        from agents.disruption_agent import run as run_disruption
        from agents.eta_agent import run as run_eta
        from agents.notification_agent import run as run_notify
        _start_threads("agent_stop", [
            (run_disruption, {"poll_interval": 5.0}),
            (run_eta, {"poll_interval": 15.0}),
            (run_notify, {"poll_interval": 10.0}),
        ])
    else:
        st.session_state.agent_stop.set()


def _do_reset():
    st.session_state.gen_stop.set()
    st.session_state.agent_stop.set()
    st.session_state.gen_toggle = False
    st.session_state.agent_toggle = False
    from scripts.reset import main as reset_main
    reset_main()
    _fetch_all.clear()


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown(f"""
    <div style="text-align:center; padding: 8px 0 12px 0;">
        <a href="{RW_URL}" target="_blank">
            <img src="{RW_LOGO}" alt="RisingWave" style="height:28px; margin-bottom:8px;" />
        </a>
        <p style="color: {BRAND_GREEN}; margin: 0; font-size: 0.7rem; text-transform: uppercase;
                  letter-spacing: 0.1em;">
            Supply Chain Control Tower
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    st.markdown(f'<p style="color:{BRAND_GREEN};font-size:0.7rem;text-transform:uppercase;'
                f'letter-spacing:0.1em;margin-bottom:8px;">Data Pipeline</p>',
                unsafe_allow_html=True)

    st.toggle("Data Generators", key="gen_toggle", on_change=_on_gen_toggle,
              help="Stream orders, warehouse events, shipments, and GPS pings")
    st.toggle("AI Agents", key="agent_toggle", on_change=_on_agent_toggle,
              help="3 autonomous agents: Disruption Response (auto-resolve), ETA Prediction, Customer Notification")
    st.toggle("Show SQL", key="show_sql",
              help="Reveal the RisingWave materialized view definitions behind each panel")

    REFRESH_OPTIONS = {"1s": 1, "2s": 2, "3s": 3, "5s": 5, "10s": 10, "30s": 30, "None": None}

    def _on_refresh_change():
        st.session_state._refresh_sec = REFRESH_OPTIONS[st.session_state._refresh_sel]

    refresh_label = st.selectbox("Refresh interval", list(REFRESH_OPTIONS.keys()), index=3,
                                 key="_refresh_sel", on_change=_on_refresh_change,
                                 help="How often the dashboard fetches fresh data from RisingWave")
    if "_refresh_sec" not in st.session_state:
        st.session_state._refresh_sec = REFRESH_OPTIONS[refresh_label]

    st.divider()

    st.markdown(f'<p style="color:{ERROR};font-size:0.7rem;text-transform:uppercase;'
                f'letter-spacing:0.1em;margin-bottom:8px;">Simulate Disruption</p>',
                unsafe_allow_html=True)

    from generators.scenarios import SCENARIOS, pick_random_scenario, resolve_scenario

    scenario_options = {f"{s['icon']} {s['name']}": s["id"] for s in SCENARIOS}
    scenario_options["🎲 Random Scenario"] = "random"

    selected = st.selectbox("Scenario", list(scenario_options.keys()),
                            index=len(scenario_options) - 1)
    scenario_id = scenario_options[selected]
    wh_override = None

    if scenario_id == "random":
        st.caption("A random disruption will strike a random warehouse.")
    else:
        s = next(s for s in SCENARIOS if s["id"] == scenario_id)
        wh_override = st.selectbox("Target Warehouse", s["warehouses"])
        st.caption(f"Delay: {s['delay_range'][0]}-{s['delay_range'][1]} min (randomized)")

    if st.button("Trigger Disruption", use_container_width=True):
        from scripts.trigger_disruption import trigger
        if scenario_id == "random":
            resolved = pick_random_scenario()
        else:
            resolved = resolve_scenario(scenario_id, wh_override)
        affected = trigger(resolved["warehouse"], resolved["delay"], resolved["detail"])
        if affected > 0:
            st.toast(f"{resolved['icon']} {resolved['name']} at {resolved['warehouse']} "
                     f"— {resolved['delay']}min delay, {affected} orders affected!", icon="🚨")
        else:
            st.toast("No pending orders to disrupt. Let generators run a bit.", icon="⚠️")

    def _do_resolve():
        from db import execute_batch, query as db_query
        import uuid
        delayed = db_query("""
            SELECT o.order_id, o.warehouse_id
            FROM orders o
            JOIN (
                SELECT DISTINCT ON (order_id) order_id, event_type
                FROM warehouse_events
                ORDER BY order_id, created_at DESC
            ) latest ON o.order_id = latest.order_id
            WHERE latest.event_type = 'delay'
        """)
        if delayed:
            stmts = [
                ("""INSERT INTO warehouse_events
                    (event_id, order_id, warehouse_id, event_type, delay_minutes, detail)
                    VALUES (%s, %s, %s, 'received', 0, 'Disruption resolved, order re-queued')""",
                 (f"WE-{uuid.uuid4().hex[:8].upper()}", d["order_id"], d["warehouse_id"]))
                for d in delayed
            ]
            execute_batch(stmts)
        return len(delayed)

    if st.button("Resolve All Disruptions", use_container_width=True):
        count = _do_resolve()
        if count > 0:
            st.toast(f"Resolved {count} disrupted orders, re-queued for processing.", icon="✅")
        else:
            st.toast("No active disruptions to resolve.", icon="ℹ️")

    st.divider()
    st.button("Reset All Data", use_container_width=True, on_click=_do_reset)

    st.markdown(f"""
    <div style="padding-top:12px; text-align:center;">
        <a href="{RW_DOCS}" target="_blank" style="color:{TEXT_MUTED};font-size:0.75rem;text-decoration:none;margin:0 8px;">Docs</a>
        <a href="{RW_GITHUB}" target="_blank" style="color:{TEXT_MUTED};font-size:0.75rem;text-decoration:none;margin:0 8px;">GitHub</a>
        <a href="{RW_CLOUD}" target="_blank" style="color:{TEXT_MUTED};font-size:0.75rem;text-decoration:none;margin:0 8px;">Cloud</a>
    </div>
    <div style="text-align:center; padding-top:8px;">
        <p style="color:{TEXT_DIM};font-size:0.6rem;">
            Powered by <a href="{RW_URL}" target="_blank" style="color:{BRAND_BLUE_LIGHT};text-decoration:none;">RisingWave</a>
            Streaming Database
        </p>
    </div>
    """, unsafe_allow_html=True)


# ── Data layer ───────────────────────────────────────────────────────────────

QUERIES = {
    # Derive counts from MVs instead of scanning raw tables
    "counts":         "SELECT "
                      "(SELECT SUM(total_orders) FROM mv_warehouse_load) AS orders, "
                      "(SELECT COUNT(*) FROM mv_order_status) AS wh_events, "
                      "(SELECT COUNT(*) FROM mv_shipment_tracking) AS shipments, "
                      "(SELECT COUNT(*) FROM gps_pings) AS gps_pings, "
                      "(SELECT COUNT(*) FROM agent_actions) AS agent_actions",
    "order_status":   "SELECT current_status, COUNT(*) AS cnt FROM mv_order_status "
                      "WHERE current_status IS NOT NULL GROUP BY current_status",
    "agent_counts":   "SELECT action_type, COUNT(*) AS cnt FROM agent_actions GROUP BY action_type",
    "warehouse_load": "SELECT * FROM mv_warehouse_load ORDER BY warehouse_id",
    "tracking":       "SELECT truck_id, lat, lon, speed_mph, "
                      "remaining_stops, destination FROM mv_shipment_tracking "
                      "WHERE lat IS NOT NULL",
    "eta":            "SELECT shipment_id, truck_id, destination, remaining_stops, speed_mph, "
                      "eta_minutes, delay_status, confidence "
                      "FROM mv_eta_predictions WHERE remaining_stops > 0 "
                      "ORDER BY eta_minutes DESC NULLS LAST LIMIT 15",
    "alerts":         "SELECT a.alert_source, a.source_id, a.affected_id, "
                      "a.delay_minutes, a.reason, a.created_at "
                      "FROM mv_delay_alerts a "
                      "LEFT JOIN agent_actions aa "
                      "  ON a.affected_id = aa.target_id "
                      "  AND aa.action_type IN ('reroute', 'resolve') "
                      "WHERE aa.target_id IS NULL "
                      "ORDER BY a.created_at DESC LIMIT 15",
    "actions":        "SELECT agent_name, action_type, target_id, reasoning, detail, created_at "
                      "FROM agent_actions ORDER BY created_at DESC LIMIT 20",
    "cascade":        "SELECT ci.warehouse_id, ci.warehouse_delay_min, ci.order_id, "
                      "ci.customer_name, ci.priority, ci.shipment_id, ci.truck_id, "
                      "ci.destination "
                      "FROM mv_cascade_impact ci "
                      "LEFT JOIN agent_actions aa "
                      "  ON ci.order_id = aa.target_id "
                      "  AND aa.action_type IN ('reroute', 'resolve') "
                      "WHERE aa.target_id IS NULL "
                      "ORDER BY ci.priority, ci.warehouse_delay_min DESC",
}


@st.cache_data(ttl=1, show_spinner=False)
def _fetch_all():
    try:
        return query_batch(QUERIES)
    except Exception:
        return {key: [] for key in QUERIES}


# ── Header ───────────────────────────────────────────────────────────────────

st.markdown(f"""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">
    <div>
        <h1 style="margin:0;font-size:1.6rem;color:#FFFFFF;font-weight:400;">
            Real-Time Decisions Powered by
            <a href="{RW_URL}" target="_blank" style="color:{BRAND_BLUE_LIGHT};text-decoration:none;">RisingWave</a>
        </h1>
        <p style="margin:0;color:{TEXT_MUTED};font-size:0.8rem;">
            AI-native supply chain visibility — streaming materialized views +
            <span style="color:{BRAND_GREEN};">autonomous AI agents</span>
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

st.write("")

if st.session_state.get("show_sql"):
    st.info(
        "**What are Materialized Views?** "
        "In RisingWave, a materialized view is a SQL query whose result is **continuously maintained** "
        "as new data arrives. Unlike traditional databases that re-run the query on each read, "
        "RisingWave incrementally updates only the affected rows, giving you fresh results in "
        "milliseconds, not minutes. Each panel below is backed by a streaming MV. "
        "Expand any section to see the SQL.",
        icon="🌊",
    )

_refresh = st.session_state.get("_refresh_sec", 5)
if _refresh is None:
    st.caption("Live dashboard — auto-refresh paused.")
else:
    st.caption(f"Live dashboard refreshing every {_refresh}s.")

# ── Single live fragment with fade-in animation ──────────────────────────────

_refresh = st.session_state.get("_refresh_sec", 5)


@st.fragment(run_every=_refresh)
def _live_dashboard():
    data = _fetch_all()

    # Live architecture diagram (visible when Show SQL is on)
    if st.session_state.get("show_sql"):
        with st.expander("Architecture — Live Data Pipeline", expanded=False):
            render_pipeline(data)

    render_kpi(data)
    st.write("")

    # ── Section 1: Unified Inventory View ───────────────────────────────
    render_section_header(
        "Unified Inventory View",
        "Fix Bottlenecks Instantly: Warehouse Optimization",
        hint="Streaming GROUP BY in <b>mv_warehouse_load</b> maintains per-warehouse counts "
             "incrementally. <b>mv_cascade_impact</b> is a 3-way streaming join that shows "
             "the full blast radius of any delay — instantly.",
    )

    col_l, col_r = st.columns(2)
    with col_l:
        render_order_funnel(data)
    with col_r:
        render_warehouse_load(data)

    render_cascade(data)

    # ── Section 2: Freight Intelligence ─────────────────────────────────
    render_section_header(
        "Freight Intelligence",
        "Stop Flying Blind: Real-Time Shipment Visibility",
        hint="RisingWave joins GPS pings with shipments in real time — no batch ETL. "
             "<b>mv_eta_predictions</b> computes ETAs with a compounding delay model, then "
             "<b>mv_delay_alerts</b> chains off it to surface both warehouse and shipment "
             "delays. One GPS ping drop cascades through the MV DAG into an actionable alert.",
    )

    render_fleet_map(data)

    col_l2, col_r2 = st.columns(2)
    with col_l2:
        render_eta(data)
    with col_r2:
        render_alerts(data)

    # ── Section 3: AI-Native Supply Chain ───────────────────────────────
    render_section_header(
        "AI-Native Supply Chain",
        "Power AI with Live Data: Autonomous Operations",
        hint="AI agents query the same streaming MVs that power this dashboard. "
             "<b>mv_delay_alerts</b> chains off <b>mv_eta_predictions</b> — RisingWave "
             "propagates changes through the MV DAG automatically.",
    )

    render_agent_actions(data)


_live_dashboard()
