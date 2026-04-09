"""Supply Chain Control Tower — Web Dashboard (Streamlit)"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from db import query

st.set_page_config(
    page_title="Supply Chain Control Tower",
    page_icon="🏭",
    layout="wide",
)

# Auto-refresh every 5 seconds
st.markdown(
    '<meta http-equiv="refresh" content="5">',
    unsafe_allow_html=True,
)

st.title("Supply Chain Control Tower")
st.caption("Real-time monitoring powered by RisingWave + AI Agent")

# ── Row 1: KPI metrics ──────────────────────────────────────────────────────

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

total_orders = int(order_df["cnt"].sum()) if not order_df.empty else 0
shipped = int(order_df.loc[order_df["current_status"] == "shipped", "cnt"].sum()) if not order_df.empty else 0
delayed = int(order_df.loc[order_df["current_status"] == "delay", "cnt"].sum()) if not order_df.empty else 0
agent_acts = int(agent_df["cnt"].sum()) if not agent_df.empty else 0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Orders", total_orders)
col2.metric("Shipped", shipped)
col3.metric("Delayed", delayed, delta=f"-{delayed}" if delayed else None, delta_color="inverse")
col4.metric("Agent Actions", agent_acts)

st.divider()

# ── Row 2: Order Funnel + Warehouse Load ─────────────────────────────────────

left, right = st.columns(2)

with left:
    st.subheader("Order Fulfillment Funnel")
    if not order_df.empty:
        status_order = ["received", "picking", "packed", "shipped", "delay"]
        order_df["current_status"] = pd.Categorical(
            order_df["current_status"], categories=status_order, ordered=True
        )
        order_df = order_df.sort_values("current_status")

        colors = {
            "received": "#3498db",
            "picking": "#f39c12",
            "packed": "#9b59b6",
            "shipped": "#2ecc71",
            "delay": "#e74c3c",
            None: "#95a5a6",
        }
        fig = px.bar(
            order_df,
            x="current_status",
            y="cnt",
            color="current_status",
            color_discrete_map=colors,
            labels={"current_status": "Status", "cnt": "Count"},
        )
        fig.update_layout(showlegend=False, height=350, margin=dict(t=10))
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("No orders yet. Start the generators.")

with right:
    st.subheader("Warehouse Load")
    try:
        wh_rows = query("SELECT * FROM mv_warehouse_load ORDER BY warehouse_id")
        if wh_rows:
            wh_df = pd.DataFrame(wh_rows)
            wh_display = wh_df.rename(columns={
                "warehouse_id": "Warehouse",
                "total_orders": "Total",
                "pending": "Pending",
                "picking": "Picking",
                "packed": "Packed",
                "shipped": "Shipped",
                "delayed": "Delayed",
                "total_delay_min": "Delay (min)",
            })
            st.dataframe(
                wh_display,
                width="stretch",
                hide_index=True,
                column_config={
                    "Delayed": st.column_config.NumberColumn(format="%d", help="Delayed orders"),
                    "Delay (min)": st.column_config.NumberColumn(format="%d"),
                },
            )

            # Stacked bar chart
            melt_cols = ["Pending", "Picking", "Packed", "Shipped", "Delayed"]
            available = [c for c in melt_cols if c in wh_display.columns]
            wh_melt = wh_display.melt(
                id_vars=["Warehouse"], value_vars=available,
                var_name="Stage", value_name="Count",
            )
            fig2 = px.bar(
                wh_melt, x="Warehouse", y="Count", color="Stage",
                color_discrete_map={
                    "Pending": "#3498db", "Picking": "#f39c12",
                    "Packed": "#9b59b6", "Shipped": "#2ecc71", "Delayed": "#e74c3c",
                },
            )
            fig2.update_layout(height=250, margin=dict(t=10))
            st.plotly_chart(fig2, width="stretch")
        else:
            st.info("No warehouse data yet.")
    except Exception as e:
        st.error(f"Error loading warehouse data: {e}")

st.divider()

# ── Row 3: Fleet ETA + Delay Alerts ─────────────────────────────────────────

left2, right2 = st.columns(2)

with left2:
    st.subheader("Fleet ETA Predictions")
    try:
        eta_rows = query(
            "SELECT shipment_id, truck_id, remaining_stops, speed_mph, "
            "eta_minutes, delay_status, confidence "
            "FROM mv_eta_predictions WHERE remaining_stops > 0 "
            "ORDER BY eta_minutes DESC LIMIT 15"
        )
        if eta_rows:
            eta_df = pd.DataFrame(eta_rows)
            eta_df["eta_minutes"] = eta_df["eta_minutes"].apply(
                lambda x: round(float(x), 1) if x else None
            )
            eta_df["confidence"] = eta_df["confidence"].apply(
                lambda x: round(float(x), 2) if x else None
            )

            def style_status(val):
                colors = {"on_time": "green", "slight_delay": "orange", "delayed": "red"}
                return f"color: {colors.get(val, 'gray')}"

            st.dataframe(
                eta_df.rename(columns={
                    "shipment_id": "Shipment", "truck_id": "Truck",
                    "remaining_stops": "Stops Left", "speed_mph": "Speed (mph)",
                    "eta_minutes": "ETA (min)", "delay_status": "Status",
                    "confidence": "Confidence",
                }),
                width="stretch", hide_index=True,
            )
        else:
            st.info("No active shipments.")
    except Exception as e:
        st.error(f"Error: {e}")

with right2:
    st.subheader("Delay Alerts")
    try:
        alert_rows = query(
            "SELECT alert_source, source_id, affected_id, delay_minutes, reason, created_at "
            "FROM mv_delay_alerts ORDER BY created_at DESC LIMIT 15"
        )
        if alert_rows:
            alert_df = pd.DataFrame(alert_rows)
            alert_df["created_at"] = pd.to_datetime(alert_df["created_at"])
            st.dataframe(
                alert_df.rename(columns={
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

st.divider()

# ── Row 4: AI Agent Actions ─────────────────────────────────────────────────

st.subheader("AI Agent Actions")

try:
    action_rows = query(
        "SELECT agent_name, action_type, target_id, reasoning, detail, created_at "
        "FROM agent_actions ORDER BY created_at DESC LIMIT 20"
    )
    if action_rows:
        action_df = pd.DataFrame(action_rows)
        action_df["created_at"] = pd.to_datetime(action_df["created_at"])

        # Summary cards
        reroutes = len(action_df[action_df["action_type"] == "reroute"])
        notifies = len(action_df[action_df["action_type"] == "notify"])
        escalations = len(action_df[action_df["action_type"] == "escalate"])

        c1, c2, c3 = st.columns(3)
        c1.metric("Reroutes", reroutes)
        c2.metric("Notifications", notifies)
        c3.metric("Escalations", escalations)

        st.dataframe(
            action_df.rename(columns={
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

st.divider()

# ── Row 5: Cascade Impact ───────────────────────────────────────────────────

st.subheader("Cascade Impact — Disrupted Orders")

try:
    cascade_rows = query(
        "SELECT warehouse_id, warehouse_delay_min, order_id, customer_name, "
        "priority, shipment_id, truck_id, destination "
        "FROM mv_cascade_impact ORDER BY priority, warehouse_delay_min DESC"
    )
    if cascade_rows:
        cascade_df = pd.DataFrame(cascade_rows)
        st.dataframe(
            cascade_df.rename(columns={
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
