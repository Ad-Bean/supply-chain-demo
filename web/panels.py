"""Dashboard panel rendering functions.

Panels are split into two categories:
- "live" panels (KPIs, tables) — refresh inside @st.fragment, no flicker
- "chart" panels (bar charts, map) — render outside the fragment so they
  don't get destroyed/recreated on every refresh cycle. They update on
  sidebar interactions or manual refresh.
"""

import streamlit as st
import pandas as pd
import plotly.express as px

from web.theme import STAGE_COLORS, SUCCESS, BRAND_GREEN, ERROR, apply_rw_layout
from web.sql_docs import show_sql


def render_kpi(data: dict):
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


def render_order_funnel(data: dict):
    st.subheader("Order Fulfillment")
    st.caption("Each order flows: received → picking → packed → shipped. "
               "Backed by `mv_order_status` materialized view.")
    show_sql("order_status")
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
        st.plotly_chart(fig, key="funnel", width="stretch")
    else:
        st.info("No orders yet. Start generators from the sidebar.")


def render_warehouse_load(data: dict):
    st.subheader("Warehouse Load")
    st.caption("Orders in each stage per warehouse. Red = delayed. "
               "Backed by `mv_warehouse_load`.")
    show_sql("warehouse_load")
    if data["warehouse_load"]:
        wh = pd.DataFrame(data["warehouse_load"])
        display = wh.rename(columns={
            "warehouse_id": "Warehouse", "total_orders": "Total",
            "pending": "Pending", "picking": "Picking", "packed": "Packed",
            "shipped": "Shipped", "delayed": "Delayed", "total_delay_min": "Delay (min)",
        })
        st.dataframe(display, width="stretch", hide_index=True)
    else:
        st.info("No warehouse data yet.")


def render_fleet_map(data: dict):
    with st.expander("Fleet Map — Live truck positions", expanded=False):
        st.caption("Live truck positions from GPS pings. Color = delay status. "
                   "Backed by `mv_shipment_tracking`.")
        show_sql("fleet_map")
        _render_fleet_map_inner(data)


def _render_fleet_map_inner(data: dict):
    if data.get("tracking"):
        df = pd.DataFrame(data["tracking"])
        df = df.dropna(subset=["lat", "lon"])
        df["lat"] = df["lat"].astype(float)
        df["lon"] = df["lon"].astype(float)
        if df.empty:
            st.info("No GPS data yet.")
            return
        df["speed_mph"] = df["speed_mph"].apply(lambda x: round(float(x), 1) if x else 0)
        df["remaining_stops"] = df["remaining_stops"].apply(lambda x: int(x) if x else 0)
        df["status"] = df.apply(
            lambda r: "Delivered" if r["remaining_stops"] == 0
            else ("On Time" if r["speed_mph"] >= 40
                  else ("Slight Delay" if r["speed_mph"] >= 25 else "Delayed")),
            axis=1,
        )
        color_map = {"On Time": BRAND_GREEN, "Slight Delay": "#F59E0B",
                     "Delayed": ERROR, "Delivered": "#6B7280"}
        fig = px.scatter_map(
            df, lat="lat", lon="lon", color="status",
            color_discrete_map=color_map,
            hover_name="truck_id",
            hover_data={"speed_mph": True, "remaining_stops": True,
                        "destination": True, "status": False, "lat": False, "lon": False},
            zoom=3,
            center={"lat": 37.5, "lon": -96},
        )
        fig.update_layout(
            height=350,
            margin=dict(t=0, b=0, l=0, r=0),
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(
                bgcolor="rgba(0,0,0,0.5)", font=dict(color="#fff", size=11),
                orientation="h", yanchor="top", y=0.99, xanchor="left", x=0.01,
            ),
            map_style="carto-darkmatter",
            uirevision="stable",
        )
        fig.update_traces(marker=dict(size=10))
        st.plotly_chart(fig, key="fleet_map", width="stretch")
    else:
        st.info("No fleet tracking data yet.")


def render_eta(data: dict):
    st.subheader("Fleet ETA Predictions")
    st.caption("ETAs computed from GPS speed + remaining stops with compounding delay factor. "
               "Backed by `mv_eta_predictions`.")
    show_sql("eta")
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


def render_alerts(data: dict):
    st.subheader("Delay Alerts")
    st.caption("Warehouse delays >10min and shipments marked as delayed. "
               "Backed by `mv_delay_alerts`, triggers AI agents.")
    show_sql("alerts")
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


def render_agent_actions(data: dict):
    st.subheader("AI Agent Actions")
    st.caption("Autonomous actions taken by 3 AI agents: "
               "Disruption Response (reroute/escalate), ETA Prediction, and Customer Notification. "
               "Each action is logged to the `agent_actions` table in RisingWave.")
    show_sql("actions")
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


def render_cascade(data: dict):
    st.subheader("Cascade Impact")
    st.caption("When a warehouse is disrupted, this view joins across orders, shipments, and trucks "
               "to show the full downstream blast radius. Backed by `mv_cascade_impact`.")
    show_sql("cascade")
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
