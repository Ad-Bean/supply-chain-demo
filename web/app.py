"""Supply Chain Control Tower — Live Streaming Dashboard (Streamlit)"""

import threading
import time
import sys
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import query

st.set_page_config(
    page_title="Supply Chain Control Tower",
    page_icon="🏭",
    layout="wide",
)

# ── Background services (generators + agent) via session_state ───────────────

if "generators_running" not in st.session_state:
    st.session_state.generators_running = False
if "agent_running" not in st.session_state:
    st.session_state.agent_running = False
if "gen_threads" not in st.session_state:
    st.session_state.gen_threads = []
if "agent_thread" not in st.session_state:
    st.session_state.agent_thread = None
if "stop_event" not in st.session_state:
    st.session_state.stop_event = threading.Event()


def start_generators():
    from generators.order_gen import run as run_orders
    from generators.warehouse_gen import run as run_warehouse
    from generators.shipment_gen import run as run_shipments
    from generators.gps_gen import run as run_gps

    st.session_state.stop_event.clear()
    threads = []
    for target, kwargs in [
        (run_orders, {"interval": 2.0}),
        (run_warehouse, {"interval": 3.0}),
        (run_shipments, {"interval": 2.0}),
        (run_gps, {"interval": 4.0}),
    ]:
        t = threading.Thread(target=target, kwargs=kwargs, daemon=True)
        t.start()
        threads.append(t)
    st.session_state.gen_threads = threads
    st.session_state.generators_running = True


def start_agent():
    from agents.disruption_agent import run as run_agent
    t = threading.Thread(target=run_agent, kwargs={"poll_interval": 5.0}, daemon=True)
    t.start()
    st.session_state.agent_thread = t
    st.session_state.agent_running = True


def trigger_disruption(warehouse_id: str, delay_minutes: int):
    from scripts.trigger_disruption import trigger
    trigger(warehouse_id, delay_minutes)


def reset_data():
    from scripts.reset import main as reset_main
    reset_main()


# ── Sidebar: Control Panel ───────────────────────────────────────────────────

with st.sidebar:
    st.header("Control Panel")

    st.subheader("Data Generators")
    if not st.session_state.generators_running:
        if st.button("Start Generators", type="primary", use_container_width=True):
            start_generators()
            st.rerun()
    else:
        st.success("Generators running")

    st.subheader("AI Agent")
    if not st.session_state.agent_running:
        if st.button("Start Agent", type="primary", use_container_width=True):
            start_agent()
            st.rerun()
    else:
        st.success("Agent watching for alerts")

    st.divider()

    st.subheader("Trigger Disruption")
    wh = st.selectbox("Warehouse", ["WH-01", "WH-02", "WH-03"], index=2)
    delay = st.slider("Delay (minutes)", 15, 90, 45)
    if st.button("TRIGGER DISRUPTION", type="primary", use_container_width=True):
        trigger_disruption(wh, delay)
        st.toast(f"Disruption triggered at {wh} ({delay}min)!", icon="🚨")

    st.divider()

    if st.button("Reset All Data", use_container_width=True):
        reset_data()
        st.toast("All data cleared!", icon="🗑️")
        st.rerun()


# ── Header ───────────────────────────────────────────────────────────────────

st.title("Supply Chain Control Tower")
st.caption("Real-time monitoring powered by RisingWave + AI Agent")

# ── Row 1: KPI Metrics (streaming) ──────────────────────────────────────────


@st.fragment(run_every=3)
def kpi_metrics():
    try:
        order_counts = query(
            "SELECT current_status, COUNT(*) AS cnt FROM mv_order_status GROUP BY current_status"
        )
        order_df = pd.DataFrame(order_counts) if order_counts else pd.DataFrame(columns=["current_status", "cnt"])
    except Exception:
        order_df = pd.DataFrame(columns=["current_status", "cnt"])

    try:
        agent_counts = query(
            "SELECT action_type, COUNT(*) AS cnt FROM agent_actions GROUP BY action_type"
        )
        agent_df = pd.DataFrame(agent_counts) if agent_counts else pd.DataFrame(columns=["action_type", "cnt"])
    except Exception:
        agent_df = pd.DataFrame(columns=["action_type", "cnt"])

    total = int(order_df["cnt"].sum()) if not order_df.empty else 0
    shipped = int(order_df.loc[order_df["current_status"] == "shipped", "cnt"].sum()) if not order_df.empty else 0
    delayed = int(order_df.loc[order_df["current_status"] == "delay", "cnt"].sum()) if not order_df.empty else 0
    agent_acts = int(agent_df["cnt"].sum()) if not agent_df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Orders", total)
    c2.metric("Shipped", shipped)
    c3.metric("Delayed", delayed, delta=f"-{delayed}" if delayed else None, delta_color="inverse")
    c4.metric("Agent Actions", agent_acts)


kpi_metrics()
st.divider()

# ── Row 2: Order Funnel + Warehouse Load (streaming) ────────────────────────

left, right = st.columns(2)

with left:
    st.subheader("Order Fulfillment Funnel")

    @st.fragment(run_every=3)
    def order_funnel():
        try:
            rows = query(
                "SELECT current_status, COUNT(*) AS cnt FROM mv_order_status GROUP BY current_status"
            )
            if rows:
                df = pd.DataFrame(rows)
                status_order = ["received", "picking", "packed", "shipped", "delay"]
                df["current_status"] = pd.Categorical(df["current_status"], categories=status_order, ordered=True)
                df = df.sort_values("current_status").dropna(subset=["current_status"])

                colors = {
                    "received": "#3498db", "picking": "#f39c12",
                    "packed": "#9b59b6", "shipped": "#2ecc71", "delay": "#e74c3c",
                }
                fig = px.bar(df, x="current_status", y="cnt", color="current_status",
                             color_discrete_map=colors,
                             labels={"current_status": "Status", "cnt": "Count"})
                fig.update_layout(showlegend=False, height=350, margin=dict(t=10))
                st.plotly_chart(fig, key="funnel_chart")
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
                wh_df = pd.DataFrame(rows)
                display = wh_df.rename(columns={
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
                             color_discrete_map={
                                 "Pending": "#3498db", "Picking": "#f39c12",
                                 "Packed": "#9b59b6", "Shipped": "#2ecc71", "Delayed": "#e74c3c",
                             })
                fig.update_layout(height=250, margin=dict(t=10))
                st.plotly_chart(fig, key="wh_chart")
            else:
                st.info("No warehouse data yet.")
        except Exception as e:
            st.error(f"Error: {e}")

    warehouse_load()

st.divider()

# ── Row 3: Fleet ETA + Delay Alerts (streaming) ─────────────────────────────

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
                st.success("No active alerts.")
        except Exception as e:
            st.error(f"Error: {e}")

    delay_alerts()

st.divider()

# ── Row 4: AI Agent Actions (streaming) ─────────────────────────────────────

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
            st.info("No agent actions yet. Trigger a disruption to see the agent respond.")
    except Exception as e:
        st.error(f"Error: {e}")


agent_actions()
st.divider()

# ── Row 5: Cascade Impact (streaming) ────────────────────────────────────────

st.subheader("Cascade Impact — Disrupted Orders")


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
            st.success("No cascading disruptions.")
    except Exception as e:
        st.error(f"Error: {e}")


cascade_impact()
