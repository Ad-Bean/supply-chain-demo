"""Supply Chain Control Tower — Live Streaming Dashboard (Streamlit)"""

import threading
import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import query_batch
from web.theme import (
    RW_ICON, RW_LOGO, RW_URL, RW_DOCS, RW_GITHUB, RW_CLOUD,
    BRAND_BLUE_LIGHT, BRAND_GREEN, TEXT_MUTED, TEXT_DIM, ERROR,
    inject_css,
)
from web.panels import (
    render_kpi, render_order_funnel, render_warehouse_load,
    render_fleet_map, render_eta, render_alerts,
    render_agent_actions, render_cascade,
)

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="RisingWave | Supply Chain Control Tower",
    page_icon=RW_ICON,
    layout="wide",
)
inject_css()

# ── Background services ──────────────────────────────────────────────────────

if "gen_stop" not in st.session_state:
    st.session_state.gen_stop = threading.Event()
if "agent_stop" not in st.session_state:
    st.session_state.agent_stop = threading.Event()


def _start_threads(stop_key, thread_configs):
    st.session_state[stop_key] = threading.Event()
    stop = st.session_state[stop_key]
    for target, kwargs in thread_configs:
        kwargs["stop_event"] = stop
        threading.Thread(target=target, kwargs=kwargs, daemon=True).start()


def _on_gen_toggle():
    if st.session_state.gen_toggle:
        from generators.order_gen import run as run_orders
        from generators.warehouse_gen import run as run_warehouse
        from generators.shipment_gen import run as run_shipments
        from generators.gps_gen import run as run_gps
        _start_threads("gen_stop", [
            (run_orders, {"interval": 2.0}),
            (run_warehouse, {"interval": 3.0}),
            (run_shipments, {"interval": 2.0}),
            (run_gps, {"interval": 4.0}),
        ])
    else:
        st.session_state.gen_stop.set()


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
              help="3 agents: Disruption Response, ETA Prediction, Customer Notification")
    st.toggle("Show SQL", key="show_sql",
              help="Reveal the RisingWave materialized view definitions behind each panel")

    REFRESH_OPTIONS = {"1s": 1, "2s": 2, "3s": 3, "5s": 5, "10s": 10, "30s": 30}
    refresh_label = st.selectbox("Refresh interval", list(REFRESH_OPTIONS.keys()), index=3,
                                 help="How often the dashboard fetches fresh data from RisingWave")
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
        from db import execute, query as db_query
        import uuid
        delayed = db_query("""
            SELECT DISTINCT o.order_id, o.warehouse_id
            FROM orders o
            JOIN warehouse_events we ON o.order_id = we.order_id
            WHERE we.event_type = 'delay'
              AND o.order_id NOT IN (
                  SELECT order_id FROM warehouse_events WHERE event_type = 'shipped'
              )
        """)
        for d in delayed:
            execute(
                """INSERT INTO warehouse_events
                   (event_id, order_id, warehouse_id, event_type, delay_minutes, detail)
                   VALUES (%s, %s, %s, 'received', 0, 'Disruption resolved, order re-queued')""",
                (f"WE-{uuid.uuid4().hex[:8].upper()}", d["order_id"], d["warehouse_id"]),
            )
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
    "order_status":   "SELECT current_status, COUNT(*) AS cnt FROM mv_order_status GROUP BY current_status",
    "agent_counts":   "SELECT action_type, COUNT(*) AS cnt FROM agent_actions GROUP BY action_type",
    "warehouse_load": "SELECT * FROM mv_warehouse_load ORDER BY warehouse_id",
    "tracking":       "SELECT DISTINCT ON (truck_id) truck_id, lat, lon, speed_mph, "
                      "remaining_stops, destination FROM mv_shipment_tracking "
                      "WHERE remaining_stops > 0 AND lat IS NOT NULL ORDER BY truck_id",
    "eta":            "SELECT shipment_id, truck_id, remaining_stops, speed_mph, "
                      "eta_minutes, delay_status, confidence "
                      "FROM mv_eta_predictions WHERE remaining_stops > 0 "
                      "ORDER BY eta_minutes DESC LIMIT 15",
    "alerts":         "SELECT alert_source, source_id, affected_id, delay_minutes, reason, created_at "
                      "FROM mv_delay_alerts ORDER BY created_at DESC LIMIT 15",
    "actions":        "SELECT agent_name, action_type, target_id, reasoning, detail, created_at "
                      "FROM agent_actions ORDER BY created_at DESC LIMIT 20",
    "cascade":        "SELECT warehouse_id, warehouse_delay_min, order_id, customer_name, "
                      "priority, shipment_id, truck_id, destination "
                      "FROM mv_cascade_impact ORDER BY priority, warehouse_delay_min DESC",
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
            Supply Chain Control Tower
        </h1>
        <p style="margin:0;color:{TEXT_MUTED};font-size:0.8rem;">
            Real-time monitoring powered by
            <a href="{RW_DOCS}" target="_blank" style="color:{BRAND_BLUE_LIGHT};text-decoration:none;">RisingWave</a>
            streaming materialized views +
            <span style="color:{BRAND_GREEN};">AI Agent</span>
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
st.caption(f"Tables refresh every {_refresh}s. Charts refresh every {_refresh * 3}s.")

# ── Charts fragment (slow refresh — less flicker) ────────────────────────────
# Charts are heavy DOM elements that flicker when rebuilt. We refresh them at
# 3x the data interval to keep them reasonably current while minimizing flicker.


@st.fragment(run_every=_refresh * 3)
def _charts():
    data = _fetch_all()
    col_l, col_r = st.columns(2)
    with col_l:
        render_order_funnel(data)
    with col_r:
        render_warehouse_load(data)
    render_fleet_map(data)


_charts()

# ── Live data fragment (tables + metrics — fast refresh, no flicker) ─────────


@st.fragment(run_every=_refresh)
def _live_data():
    data = _fetch_all()
    render_kpi(data)
    st.write("")
    col_l2, col_r2 = st.columns(2)
    with col_l2:
        render_eta(data)
    with col_r2:
        render_alerts(data)
    render_agent_actions(data)
    render_cascade(data)


_live_data()
