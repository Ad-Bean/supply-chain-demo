"""Supply Chain Control Tower — Live Streaming Dashboard (Streamlit)
Branded with RisingWave design system."""

import threading
import sys
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import query

# ── RisingWave brand tokens ─────────────────────────────────────────────────

BRAND_BLUE = "#005EEC"
BRAND_BLUE_LIGHT = "#337EF0"
BRAND_GREEN = "#62F4C0"
BRAND_GREEN_DARK = "#039777"
BG_DARK = "#081F29"
BG_ELEVATED = "#0A3246"
BG_CARD = "#0C2535"
TEXT_MUTED = "#A0A0AB"
TEXT_DIM = "#70707B"
BORDER_DARK = "rgba(255,255,255,0.1)"
SUCCESS = "#10B981"
WARNING = "#F59E0B"
ERROR = "#EF4444"
INFO = "#3B82F6"

# Chart palette matching brand
STAGE_COLORS = {
    "received": BRAND_BLUE,
    "picking": WARNING,
    "packed": "#8B5CF6",
    "shipped": BRAND_GREEN,
    "delay": ERROR,
    "Pending": BRAND_BLUE,
    "Picking": WARNING,
    "Packed": "#8B5CF6",
    "Shipped": BRAND_GREEN,
    "Delayed": ERROR,
}

st.set_page_config(
    page_title="RisingWave | Supply Chain Control Tower",
    page_icon="🌊",
    layout="wide",
)

# ── Custom CSS for RisingWave look ───────────────────────────────────────────

st.markdown(f"""
<style>
    /* Header bar */
    header[data-testid="stHeader"] {{
        background-color: {BG_DARK};
    }}

    /* Metric cards */
    div[data-testid="stMetric"] {{
        background: {BG_CARD};
        border: 1px solid {BORDER_DARK};
        border-radius: 8px;
        padding: 12px 16px;
    }}
    div[data-testid="stMetric"] label {{
        color: {TEXT_MUTED};
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
        color: #FFFFFF;
        font-size: 1.8rem;
    }}

    /* Subheaders */
    h3 {{
        color: {BRAND_GREEN} !important;
        font-size: 1rem !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}

    /* Tables */
    div[data-testid="stDataFrame"] {{
        border: 1px solid {BORDER_DARK};
        border-radius: 8px;
    }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background-color: {BG_CARD};
        border-right: 1px solid {BORDER_DARK};
    }}

    /* Disruption button styling */
    .disruption-btn button {{
        background-color: {ERROR} !important;
        border-color: {ERROR} !important;
    }}

    /* Plotly chart backgrounds */
    .stPlotlyChart {{
        border: 1px solid {BORDER_DARK};
        border-radius: 8px;
        overflow: hidden;
    }}
</style>
""", unsafe_allow_html=True)

# ── Background services ──────────────────────────────────────────────────────

if "generators_running" not in st.session_state:
    st.session_state.generators_running = False
if "agent_running" not in st.session_state:
    st.session_state.agent_running = False
if "gen_stop" not in st.session_state:
    st.session_state.gen_stop = threading.Event()
if "agent_stop" not in st.session_state:
    st.session_state.agent_stop = threading.Event()


def start_generators():
    from generators.order_gen import run as run_orders
    from generators.warehouse_gen import run as run_warehouse
    from generators.shipment_gen import run as run_shipments
    from generators.gps_gen import run as run_gps

    st.session_state.gen_stop.clear()
    stop = st.session_state.gen_stop
    for target, kwargs in [
        (run_orders, {"interval": 2.0, "stop_event": stop}),
        (run_warehouse, {"interval": 3.0, "stop_event": stop}),
        (run_shipments, {"interval": 2.0, "stop_event": stop}),
        (run_gps, {"interval": 4.0, "stop_event": stop}),
    ]:
        threading.Thread(target=target, kwargs=kwargs, daemon=True).start()
    st.session_state.generators_running = True


def stop_generators():
    st.session_state.gen_stop.set()
    st.session_state.generators_running = False


def start_agent():
    from agents.disruption_agent import run as run_agent

    st.session_state.agent_stop.clear()
    threading.Thread(
        target=run_agent,
        kwargs={"poll_interval": 5.0, "stop_event": st.session_state.agent_stop},
        daemon=True,
    ).start()
    st.session_state.agent_running = True


def stop_agent():
    st.session_state.agent_stop.set()
    st.session_state.agent_running = False


# ── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    # RisingWave logo/brand
    st.markdown(f"""
    <div style="text-align:center; padding: 8px 0 16px 0;">
        <span style="font-size: 2rem;">🌊</span>
        <h2 style="color: #FFFFFF; margin: 4px 0 0 0; font-size: 1.3rem; letter-spacing: -0.02em;">
            RisingWave
        </h2>
        <p style="color: {BRAND_GREEN}; margin: 0; font-size: 0.7rem; text-transform: uppercase;
                  letter-spacing: 0.1em;">
            Supply Chain Control Tower
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Data pipeline controls
    st.markdown(f'<p style="color:{BRAND_GREEN};font-size:0.7rem;text-transform:uppercase;'
                f'letter-spacing:0.1em;margin-bottom:8px;">Data Pipeline</p>',
                unsafe_allow_html=True)

    if not st.session_state.generators_running:
        if st.button("Start Generators", type="primary", use_container_width=True):
            start_generators()
            st.rerun()
    else:
        gc1, gc2 = st.columns([3, 1])
        with gc1:
            st.markdown(f'<div style="background:{BG_ELEVATED};border:1px solid {BRAND_GREEN};'
                        f'border-radius:6px;padding:8px 12px;text-align:center;">'
                        f'<span style="color:{BRAND_GREEN};">&#9679;</span> '
                        f'<span style="color:#fff;font-size:0.85rem;">Active</span></div>',
                        unsafe_allow_html=True)
        with gc2:
            if st.button("Stop", key="stop_gen", use_container_width=True):
                stop_generators()
                st.rerun()

    st.write("")

    if not st.session_state.agent_running:
        if st.button("Start AI Agent", type="primary", use_container_width=True):
            start_agent()
            st.rerun()
    else:
        ac1, ac2 = st.columns([3, 1])
        with ac1:
            st.markdown(f'<div style="background:{BG_ELEVATED};border:1px solid {BRAND_BLUE};'
                        f'border-radius:6px;padding:8px 12px;text-align:center;">'
                        f'<span style="color:{BRAND_BLUE_LIGHT};">&#9679;</span> '
                        f'<span style="color:#fff;font-size:0.85rem;">Watching</span></div>',
                        unsafe_allow_html=True)
        with ac2:
            if st.button("Stop", key="stop_agent", use_container_width=True):
                stop_agent()
                st.rerun()

    st.divider()

    # Disruption trigger
    st.markdown(f'<p style="color:{ERROR};font-size:0.7rem;text-transform:uppercase;'
                f'letter-spacing:0.1em;margin-bottom:8px;">Simulate Disruption</p>',
                unsafe_allow_html=True)

    wh = st.selectbox("Warehouse", ["WH-01", "WH-02", "WH-03"], index=2)
    delay = st.slider("Delay (minutes)", 15, 90, 45)
    if st.button("TRIGGER DISRUPTION", use_container_width=True):
        from scripts.trigger_disruption import trigger
        trigger(wh, delay)
        st.toast(f"Disruption triggered at {wh} ({delay}min)!", icon="🚨")

    st.divider()

    if st.button("Reset All Data", use_container_width=True):
        from scripts.reset import main as reset_main
        reset_main()
        st.toast("All data cleared!", icon="🗑️")
        st.rerun()

    # Footer
    st.markdown(f"""
    <div style="position:fixed;bottom:12px;left:16px;right:16px;text-align:center;">
        <p style="color:{TEXT_DIM};font-size:0.65rem;">
            Powered by <span style="color:{BRAND_BLUE_LIGHT};">RisingWave</span> Streaming Database
            &nbsp;|&nbsp; Real-time Materialized Views
        </p>
    </div>
    """, unsafe_allow_html=True)


# ── Plotly theme helper ──────────────────────────────────────────────────────

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


# ── Header ───────────────────────────────────────────────────────────────────

st.markdown(f"""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:4px;">
    <span style="font-size:1.6rem;">🏭</span>
    <div>
        <h1 style="margin:0;font-size:1.8rem;color:#FFFFFF;font-weight:400;">
            Supply Chain Control Tower
        </h1>
        <p style="margin:0;color:{TEXT_MUTED};font-size:0.85rem;">
            Real-time monitoring powered by
            <span style="color:{BRAND_BLUE_LIGHT};">RisingWave</span>
            streaming materialized views +
            <span style="color:{BRAND_GREEN};">AI Agent</span>
        </p>
    </div>
</div>
""", unsafe_allow_html=True)

st.write("")

# ── Row 1: KPI Metrics ──────────────────────────────────────────────────────


@st.fragment(run_every=3)
def kpi_metrics():
    try:
        order_counts = query(
            "SELECT current_status, COUNT(*) AS cnt FROM mv_order_status GROUP BY current_status"
        )
        odf = pd.DataFrame(order_counts) if order_counts else pd.DataFrame(columns=["current_status", "cnt"])
    except Exception:
        odf = pd.DataFrame(columns=["current_status", "cnt"])

    try:
        agent_counts = query(
            "SELECT action_type, COUNT(*) AS cnt FROM agent_actions GROUP BY action_type"
        )
        adf = pd.DataFrame(agent_counts) if agent_counts else pd.DataFrame(columns=["action_type", "cnt"])
    except Exception:
        adf = pd.DataFrame(columns=["action_type", "cnt"])

    total = int(odf["cnt"].sum()) if not odf.empty else 0
    shipped = int(odf.loc[odf["current_status"] == "shipped", "cnt"].sum()) if not odf.empty else 0
    delayed = int(odf.loc[odf["current_status"] == "delay", "cnt"].sum()) if not odf.empty else 0
    agent_acts = int(adf["cnt"].sum()) if not adf.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Orders", total)
    c2.metric("Shipped", shipped)
    c3.metric("Delayed", delayed, delta=f"-{delayed}" if delayed else None, delta_color="inverse")
    c4.metric("Agent Actions", agent_acts)


kpi_metrics()
st.write("")

# ── Row 2: Order Funnel + Warehouse Load ─────────────────────────────────────

left, right = st.columns(2)

with left:
    st.subheader("Order Fulfillment")

    @st.fragment(run_every=3)
    def order_funnel():
        try:
            rows = query(
                "SELECT current_status, COUNT(*) AS cnt FROM mv_order_status GROUP BY current_status"
            )
            if rows:
                df = pd.DataFrame(rows)
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
        except Exception as e:
            st.error(f"Error: {e}")

    order_funnel()

with right:
    st.subheader("Warehouse Load")

    @st.fragment(run_every=3)
    def warehouse_load():
        try:
            rows = query("SELECT * FROM mv_warehouse_load ORDER BY warehouse_id")
            if rows:
                wh = pd.DataFrame(rows)
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
        except Exception as e:
            st.error(f"Error: {e}")

    warehouse_load()

# ── Row 3: Fleet ETA + Alerts ────────────────────────────────────────────────

left2, right2 = st.columns(2)

with left2:
    st.subheader("Fleet ETA Predictions")

    @st.fragment(run_every=4)
    def fleet_eta():
        try:
            rows = query(
                "SELECT shipment_id, truck_id, remaining_stops, speed_mph, "
                "eta_minutes, delay_status, confidence "
                "FROM mv_eta_predictions WHERE remaining_stops > 0 "
                "ORDER BY eta_minutes DESC LIMIT 15"
            )
            if rows:
                df = pd.DataFrame(rows)
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
        except Exception as e:
            st.error(f"Error: {e}")

    fleet_eta()

with right2:
    st.subheader("Delay Alerts")

    @st.fragment(run_every=3)
    def delay_alerts():
        try:
            rows = query(
                "SELECT alert_source, source_id, affected_id, delay_minutes, reason, created_at "
                "FROM mv_delay_alerts ORDER BY created_at DESC LIMIT 15"
            )
            if rows:
                df = pd.DataFrame(rows)
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
        except Exception as e:
            st.error(f"Error: {e}")

    delay_alerts()

# ── Row 4: AI Agent Actions ──────────────────────────────────────────────────

st.subheader("AI Agent Actions")


@st.fragment(run_every=3)
def agent_actions():
    try:
        rows = query(
            "SELECT agent_name, action_type, target_id, reasoning, detail, created_at "
            "FROM agent_actions ORDER BY created_at DESC LIMIT 20"
        )
        if rows:
            df = pd.DataFrame(rows)
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
    except Exception as e:
        st.error(f"Error: {e}")


agent_actions()

# ── Row 5: Cascade Impact ───────────────────────────────────────────────────

st.subheader("Cascade Impact")


@st.fragment(run_every=3)
def cascade_impact():
    try:
        rows = query(
            "SELECT warehouse_id, warehouse_delay_min, order_id, customer_name, "
            "priority, shipment_id, truck_id, destination "
            "FROM mv_cascade_impact ORDER BY priority, warehouse_delay_min DESC"
        )
        if rows:
            df = pd.DataFrame(rows)
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
    except Exception as e:
        st.error(f"Error: {e}")


cascade_impact()
