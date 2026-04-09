"""Supply Chain Control Tower — Live Streaming Dashboard (Streamlit)
Branded with RisingWave design system."""

import threading
import sys
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import query

# ── RisingWave brand tokens ─────────────────────────────────────────────────

BRAND_BLUE = "#005EEC"
BRAND_BLUE_LIGHT = "#337EF0"
BRAND_GREEN = "#62F4C0"
BG_DARK = "#081F29"
BG_ELEVATED = "#0A3246"
BG_CARD = "#0C2535"
TEXT_MUTED = "#A0A0AB"
TEXT_DIM = "#70707B"
BORDER_DARK = "rgba(255,255,255,0.1)"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
ERROR = "#EF4444"

RW_LOGO = "https://www.risingwave.com/_next/static/media/risingwave-logo-white-text.86234334.svg"
RW_ICON = "https://www.risingwave.com/metadata/icon.svg"
RW_URL = "https://www.risingwave.com"
RW_DOCS = "https://docs.risingwave.com"
RW_GITHUB = "https://github.com/risingwavelabs/risingwave"
RW_CLOUD = "https://cloud.risingwave.com"

STAGE_COLORS = {
    "received": BRAND_BLUE, "picking": WARNING, "packed": "#8B5CF6",
    "shipped": BRAND_GREEN, "delay": ERROR,
    "Pending": BRAND_BLUE, "Picking": WARNING, "Packed": "#8B5CF6",
    "Shipped": BRAND_GREEN, "Delayed": ERROR,
}

st.set_page_config(
    page_title="RisingWave | Supply Chain Control Tower",
    page_icon=RW_ICON,
    layout="wide",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown(f"""
<style>
    header[data-testid="stHeader"] {{ background-color: {BG_DARK}; }}
    div[data-testid="stMetric"] {{
        background: {BG_CARD}; border: 1px solid {BORDER_DARK};
        border-radius: 8px; padding: 12px 16px;
    }}
    div[data-testid="stMetric"] label {{
        color: {TEXT_MUTED}; font-size: 0.75rem;
        text-transform: uppercase; letter-spacing: 0.05em;
    }}
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
        color: #FFFFFF; font-size: 1.8rem;
    }}
    h3 {{ color: {BRAND_GREEN} !important; font-size: 1rem !important;
         text-transform: uppercase; letter-spacing: 0.08em; }}
    div[data-testid="stDataFrame"] {{
        border: 1px solid {BORDER_DARK}; border-radius: 8px;
    }}
    section[data-testid="stSidebar"] {{
        background-color: {BG_CARD}; border-right: 1px solid {BORDER_DARK};
    }}
    .stPlotlyChart {{
        border: 1px solid {BORDER_DARK}; border-radius: 8px; overflow: hidden;
    }}
</style>
""", unsafe_allow_html=True)

# ── Background services ──────────────────────────────────────────────────────

if "gen_stop" not in st.session_state:
    st.session_state.gen_stop = threading.Event()
if "agent_stop" not in st.session_state:
    st.session_state.agent_stop = threading.Event()


def _start_threads(toggle_key, stop_key, thread_configs):
    """Generic helper: create fresh stop event and spawn threads."""
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
        _start_threads("gen_toggle", "gen_stop", [
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
        _start_threads("agent_toggle", "agent_stop", [
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

    st.divider()

    st.markdown(f'<p style="color:{ERROR};font-size:0.7rem;text-transform:uppercase;'
                f'letter-spacing:0.1em;margin-bottom:8px;">Simulate Disruption</p>',
                unsafe_allow_html=True)

    from generators.scenarios import SCENARIOS, pick_random_scenario, resolve_scenario

    scenario_options = {f"{s['icon']} {s['name']}": s["id"] for s in SCENARIOS}
    scenario_options["🎲 Random Scenario"] = "random"

    selected = st.selectbox("Scenario", list(scenario_options.keys()), index=len(scenario_options) - 1)
    scenario_id = scenario_options[selected]

    if scenario_id == "random":
        # Show preview of what random might pick
        st.caption("A random disruption will strike a random warehouse.")
    else:
        s = next(s for s in SCENARIOS if s["id"] == scenario_id)
        wh_override = st.selectbox("Target Warehouse", s["warehouses"])
        st.caption(f"Delay: {s['delay_range'][0]}-{s['delay_range'][1]} min (randomized)")

    if st.button("TRIGGER DISRUPTION", use_container_width=True):
        from scripts.trigger_disruption import trigger

        if scenario_id == "random":
            resolved = pick_random_scenario()
        else:
            resolved = resolve_scenario(scenario_id, wh_override)

        affected = trigger(resolved["warehouse"], resolved["delay"], resolved["detail"])

        if affected > 0:
            st.toast(
                f"{resolved['icon']} {resolved['name']} at {resolved['warehouse']} "
                f"— {resolved['delay']}min delay, {affected} orders affected!",
                icon="🚨",
            )
        else:
            st.toast("No pending orders to disrupt. Let generators run a bit.", icon="⚠️")

    # Resolve active disruptions
    def _do_resolve():
        from db import execute, query as db_query
        import uuid
        # Find all orders stuck in 'delay' and move them back to 'received'
        # so the warehouse pipeline can re-process them
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
                   VALUES (%s, %s, %s, 'received', 0, 'Disruption resolved — order re-queued')""",
                (f"WE-{uuid.uuid4().hex[:8].upper()}", d["order_id"], d["warehouse_id"]),
            )
        return len(delayed)

    if st.button("Resolve All Disruptions", use_container_width=True):
        count = _do_resolve()
        if count > 0:
            st.toast(f"Resolved {count} disrupted orders — re-queued for processing.", icon="✅")
        else:
            st.toast("No active disruptions to resolve.", icon="ℹ️")

    st.divider()

    st.button("Reset All Data", use_container_width=True, on_click=_do_reset)

    # Links
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


# ── Plotly theme ─────────────────────────────────────────────────────────────

def apply_rw_layout(fig, height=350):
    fig.update_layout(
        height=height,
        margin=dict(t=10, b=30, l=40, r=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor=BG_CARD,
        font=dict(color=TEXT_MUTED, size=12),
        xaxis=dict(gridcolor=BORDER_DARK, zerolinecolor=BORDER_DARK),
        yaxis=dict(gridcolor=BORDER_DARK, zerolinecolor=BORDER_DARK),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_MUTED)),
    )
    return fig


# ── Cached data layer ────────────────────────────────────────────────────────

QUERIES = {
    "order_status":   "SELECT current_status, COUNT(*) AS cnt FROM mv_order_status GROUP BY current_status",
    "agent_counts":   "SELECT action_type, COUNT(*) AS cnt FROM agent_actions GROUP BY action_type",
    "warehouse_load": "SELECT * FROM mv_warehouse_load ORDER BY warehouse_id",
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


@st.cache_data(ttl=3, show_spinner=False)
def _fetch_all():
    return {key: _safe_query(sql) for key, sql in QUERIES.items()}


def _safe_query(sql):
    try:
        return query(sql)
    except Exception:
        return []


# ── Static layout + independent streaming fragments ──────────────────────────
# Layout (headers, columns) renders ONCE. Each @st.fragment only re-renders
# its own content. Shared cache means 1 DB call per 3s total.

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

# ── KPI Metrics ──────────────────────────────────────────────────────────────

kpi_slot = st.container()


@st.fragment(run_every=5)
def _kpi():
    data = _fetch_all()
    odf = pd.DataFrame(data["order_status"]) if data["order_status"] else pd.DataFrame(columns=["current_status", "cnt"])
    adf = pd.DataFrame(data["agent_counts"]) if data["agent_counts"] else pd.DataFrame(columns=["action_type", "cnt"])

    total = int(odf["cnt"].sum()) if not odf.empty else 0
    shipped = int(odf.loc[odf["current_status"] == "shipped", "cnt"].sum()) if not odf.empty else 0
    delayed = int(odf.loc[odf["current_status"] == "delay", "cnt"].sum()) if not odf.empty else 0
    agent_acts = int(adf["cnt"].sum()) if not adf.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Orders", total)
    c2.metric("Shipped", shipped)
    c3.metric("Delayed", delayed)
    c4.metric("Agent Actions", agent_acts)


with kpi_slot:
    _kpi()

st.write("")

# ── Order Funnel + Warehouse Load ────────────────────────────────────────────

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Order Fulfillment")

    @st.fragment(run_every=5)
    def _funnel():
        data = _fetch_all()
        if data["order_status"]:
            df = pd.DataFrame(data["order_status"])
            cats = ["received", "picking", "packed", "shipped", "delay"]
            df["current_status"] = pd.Categorical(df["current_status"], categories=cats, ordered=True)
            df = df.sort_values("current_status").dropna(subset=["current_status"])
            fig = px.bar(df, x="current_status", y="cnt", color="current_status",
                         color_discrete_map=STAGE_COLORS,
                         labels={"current_status": "Status", "cnt": "Count"})
            fig.update_layout(showlegend=False)
            apply_rw_layout(fig, height=340)
            st.plotly_chart(fig, key="funnel")
        else:
            st.info("No orders yet. Start generators from the sidebar.")

    _funnel()

with col_right:
    st.subheader("Warehouse Load")

    @st.fragment(run_every=5)
    def _warehouse():
        data = _fetch_all()
        if data["warehouse_load"]:
            wh = pd.DataFrame(data["warehouse_load"])
            display = wh.rename(columns={
                "warehouse_id": "Warehouse", "total_orders": "Total",
                "pending": "Pending", "picking": "Picking", "packed": "Packed",
                "shipped": "Shipped", "delayed": "Delayed", "total_delay_min": "Delay (min)",
            })
            st.dataframe(display, width="stretch", hide_index=True)
            melt_cols = ["Pending", "Picking", "Packed", "Shipped", "Delayed"]
            available = [c for c in melt_cols if c in display.columns]
            melted = display.melt(id_vars=["Warehouse"], value_vars=available,
                                  var_name="Stage", value_name="Count")
            fig = px.bar(melted, x="Warehouse", y="Count", color="Stage",
                         color_discrete_map=STAGE_COLORS)
            apply_rw_layout(fig, height=220)
            st.plotly_chart(fig, key="wh_chart")
        else:
            st.info("No warehouse data yet.")

    _warehouse()

# ── Fleet ETA + Alerts ───────────────────────────────────────────────────────

col_left2, col_right2 = st.columns(2)

with col_left2:
    st.subheader("Fleet ETA Predictions")

    @st.fragment(run_every=5)
    def _eta():
        data = _fetch_all()
        if data["eta"]:
            df = pd.DataFrame(data["eta"])
            df["eta_minutes"] = df["eta_minutes"].apply(lambda x: round(float(x), 1) if x else None)
            df["confidence"] = df["confidence"].apply(lambda x: round(float(x), 2) if x else None)
            st.dataframe(
                df.rename(columns={
                    "shipment_id": "Shipment", "truck_id": "Truck",
                    "remaining_stops": "Stops Left", "speed_mph": "Speed",
                    "eta_minutes": "ETA (min)", "delay_status": "Status",
                    "confidence": "Confidence",
                }),
                width="stretch", hide_index=True,
            )
        else:
            st.info("No active shipments.")

    _eta()

with col_right2:
    st.subheader("Delay Alerts")

    @st.fragment(run_every=5)
    def _alerts():
        data = _fetch_all()
        if data["alerts"]:
            df = pd.DataFrame(data["alerts"])
            df["created_at"] = pd.to_datetime(df["created_at"])
            st.dataframe(
                df.rename(columns={
                    "alert_source": "Source", "source_id": "Origin",
                    "affected_id": "Order", "delay_minutes": "Delay (min)",
                    "reason": "Reason", "created_at": "Time",
                }),
                width="stretch", hide_index=True,
            )
        else:
            st.markdown(f'<p style="color:{SUCCESS};">No active alerts.</p>',
                        unsafe_allow_html=True)

    _alerts()

# ── AI Agent Actions ─────────────────────────────────────────────────────────

st.subheader("AI Agent Actions")


@st.fragment(run_every=5)
def _agent_actions():
    data = _fetch_all()
    if data["actions"]:
        df = pd.DataFrame(data["actions"])
        df["created_at"] = pd.to_datetime(df["created_at"])
        reroutes = len(df[df["action_type"] == "reroute"])
        notifies = len(df[df["action_type"] == "notify"])
        escalations = len(df[df["action_type"] == "escalate"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Reroutes", reroutes)
        c2.metric("Notifications", notifies)
        c3.metric("Escalations", escalations)
        st.dataframe(
            df.rename(columns={
                "agent_name": "Agent", "action_type": "Action",
                "target_id": "Target", "reasoning": "Reasoning",
                "detail": "Detail", "created_at": "Time",
            }),
            width="stretch", hide_index=True,
        )
    else:
        st.info("No agent actions yet. Trigger a disruption to see the AI agent respond.")


_agent_actions()

# ── Cascade Impact ───────────────────────────────────────────────────────────

st.subheader("Cascade Impact")


@st.fragment(run_every=5)
def _cascade():
    data = _fetch_all()
    if data["cascade"]:
        df = pd.DataFrame(data["cascade"])
        st.dataframe(
            df.rename(columns={
                "warehouse_id": "Warehouse", "warehouse_delay_min": "Delay (min)",
                "order_id": "Order", "customer_name": "Customer",
                "priority": "Priority", "shipment_id": "Shipment",
                "truck_id": "Truck", "destination": "Destination",
            }),
            width="stretch", hide_index=True,
        )
    else:
        st.markdown(f'<p style="color:{SUCCESS};">No cascading disruptions.</p>',
                    unsafe_allow_html=True)


_cascade()
