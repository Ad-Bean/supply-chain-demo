"""Supply Chain Control Tower — Live Dashboard (Dash + Plotly)

Run: PYTHONPATH=. .venv/bin/python3 web/app.py
"""

import threading
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import dash
from dash import html, dcc, dash_table, callback, Input, Output, State, ctx
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from db import query_batch
from web.theme import (
    BRAND_BLUE, BRAND_BLUE_LIGHT, BRAND_GREEN, BG_DARK, BG_ELEVATED, BG_CARD,
    TEXT_MUTED, TEXT_DIM, BORDER_DARK, SUCCESS, WARNING, ERROR,
    RW_LOGO, RW_ICON, RW_URL, RW_DOCS, RW_GITHUB, RW_CLOUD,
    STAGE_COLORS, apply_rw_layout,
)
from web.sql_docs import MV_SQL

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


def fetch_all():
    try:
        return query_batch(QUERIES)
    except Exception:
        return {key: [] for key in QUERIES}


# ── Background services ──────────────────────────────────────────────────────

_gen_stop = threading.Event()
_agent_stop = threading.Event()
_gen_running = False
_agent_running = False


def start_generators():
    global _gen_stop, _gen_running
    if _gen_running:
        return
    _gen_stop = threading.Event()
    from generators.order_gen import run as run_orders
    from generators.warehouse_gen import run as run_warehouse
    from generators.shipment_gen import run as run_shipments
    from generators.gps_gen import run as run_gps
    for target, kwargs in [
        (run_orders, {"interval": 2.0, "stop_event": _gen_stop}),
        (run_warehouse, {"interval": 3.0, "stop_event": _gen_stop}),
        (run_shipments, {"interval": 2.0, "stop_event": _gen_stop}),
        (run_gps, {"interval": 4.0, "stop_event": _gen_stop}),
    ]:
        threading.Thread(target=target, kwargs=kwargs, daemon=True).start()
    _gen_running = True


def stop_generators():
    global _gen_running
    _gen_stop.set()
    _gen_running = False


def start_agents():
    global _agent_stop, _agent_running
    if _agent_running:
        return
    _agent_stop = threading.Event()
    from agents.disruption_agent import run as run_disruption
    from agents.eta_agent import run as run_eta
    from agents.notification_agent import run as run_notify
    for target, kwargs in [
        (run_disruption, {"poll_interval": 5.0, "stop_event": _agent_stop}),
        (run_eta, {"poll_interval": 15.0, "stop_event": _agent_stop}),
        (run_notify, {"poll_interval": 10.0, "stop_event": _agent_stop}),
    ]:
        threading.Thread(target=target, kwargs=kwargs, daemon=True).start()
    _agent_running = True


def stop_agents():
    global _agent_running
    _agent_stop.set()
    _agent_running = False


# ── Dash App ─────────────────────────────────────────────────────────────────

app = dash.Dash(
    __name__,
    title="RisingWave | Supply Chain Control Tower",
    update_title=None,  # don't show "Updating..." in tab
)

# ── CSS ──────────────────────────────────────────────────────────────────────

CARD_STYLE = {
    "background": BG_CARD, "border": f"1px solid {BORDER_DARK}",
    "borderRadius": "8px", "padding": "16px", "marginBottom": "12px",
}
METRIC_STYLE = {
    **CARD_STYLE, "textAlign": "center", "flex": "1",
}
SECTION_TITLE = {
    "color": BRAND_GREEN, "fontSize": "0.9rem", "textTransform": "uppercase",
    "letterSpacing": "0.08em", "marginBottom": "8px", "marginTop": "16px",
}
TABLE_STYLE_HEADER = {
    "backgroundColor": BG_ELEVATED, "color": "#fff",
    "fontWeight": "500", "fontSize": "0.8rem", "border": f"1px solid {BORDER_DARK}",
}
TABLE_STYLE_DATA = {
    "backgroundColor": BG_CARD, "color": TEXT_MUTED,
    "fontSize": "0.8rem", "border": f"1px solid {BORDER_DARK}",
}
TABLE_STYLE_CELL = {
    "textAlign": "left", "padding": "8px", "overflow": "hidden",
    "textOverflow": "ellipsis", "maxWidth": "200px",
}


def make_metric(label, value, id_suffix):
    return html.Div(style=METRIC_STYLE, children=[
        html.Div(label, style={"color": TEXT_MUTED, "fontSize": "0.7rem",
                                "textTransform": "uppercase", "letterSpacing": "0.05em"}),
        html.Div(id=f"metric-{id_suffix}", children=str(value),
                 style={"color": "#fff", "fontSize": "1.8rem", "fontWeight": "400"}),
    ])


def make_table(id, columns):
    return dash_table.DataTable(
        id=id, columns=[{"name": c, "id": c} for c in columns],
        data=[], page_size=10,
        style_header=TABLE_STYLE_HEADER,
        style_data=TABLE_STYLE_DATA,
        style_cell=TABLE_STYLE_CELL,
        style_table={"overflowX": "auto"},
    )


# ── Layout ───────────────────────────────────────────────────────────────────

app.layout = html.Div(style={"backgroundColor": BG_DARK, "minHeight": "100vh",
                              "color": "#fff", "fontFamily": "Inter, sans-serif"}, children=[

    # Interval timer
    dcc.Interval(id="interval", interval=5000, n_intervals=0),

    # Header
    html.Div(style={"padding": "16px 24px", "display": "flex", "alignItems": "center",
                     "gap": "16px", "borderBottom": f"1px solid {BORDER_DARK}"}, children=[
        html.A(href=RW_URL, target="_blank", children=[
            html.Img(src=RW_LOGO, style={"height": "28px"}),
        ]),
        html.Div(children=[
            html.H1("Supply Chain Control Tower",
                     style={"margin": "0", "fontSize": "1.4rem", "fontWeight": "400"}),
            html.P([
                "Real-time monitoring powered by ",
                html.A("RisingWave", href=RW_DOCS, target="_blank",
                       style={"color": BRAND_BLUE_LIGHT, "textDecoration": "none"}),
                " streaming materialized views + ",
                html.Span("AI Agent", style={"color": BRAND_GREEN}),
            ], style={"margin": "0", "color": TEXT_MUTED, "fontSize": "0.8rem"}),
        ]),
        # Controls
        html.Div(style={"marginLeft": "auto", "display": "flex", "gap": "8px",
                         "alignItems": "center"}, children=[
            html.Button("Start Generators", id="btn-gen", n_clicks=0,
                        style={"padding": "6px 14px", "borderRadius": "6px", "border": "none",
                               "background": BRAND_BLUE, "color": "#fff", "cursor": "pointer",
                               "fontSize": "0.8rem"}),
            html.Button("Start Agents", id="btn-agent", n_clicks=0,
                        style={"padding": "6px 14px", "borderRadius": "6px", "border": "none",
                               "background": BRAND_GREEN, "color": BG_DARK, "cursor": "pointer",
                               "fontSize": "0.8rem"}),
            html.Button("Trigger Disruption", id="btn-disrupt", n_clicks=0,
                        style={"padding": "6px 14px", "borderRadius": "6px", "border": "none",
                               "background": ERROR, "color": "#fff", "cursor": "pointer",
                               "fontSize": "0.8rem"}),
            html.Button("Reset", id="btn-reset", n_clicks=0,
                        style={"padding": "6px 14px", "borderRadius": "6px", "border": "none",
                               "background": TEXT_DIM, "color": "#fff", "cursor": "pointer",
                               "fontSize": "0.8rem"}),
            dcc.Dropdown(
                id="refresh-dropdown",
                options=[{"label": f"{s}s", "value": s * 1000} for s in [1, 2, 3, 5, 10, 30]],
                value=5000, clearable=False,
                style={"width": "80px", "fontSize": "0.8rem"},
            ),
            html.Div(id="status-text", style={"color": TEXT_MUTED, "fontSize": "0.75rem"}),
        ]),
    ]),

    # Main content
    html.Div(style={"padding": "16px 24px"}, children=[

        # KPI metrics row
        html.Div(style={"display": "flex", "gap": "12px", "marginBottom": "16px"}, children=[
            make_metric("Total Orders", "0", "total"),
            make_metric("Shipped", "0", "shipped"),
            make_metric("Delayed", "0", "delayed"),
            make_metric("Agent Actions", "0", "actions"),
        ]),

        # Row 2: Order Funnel + Warehouse Load
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"}, children=[
            html.Div(style=CARD_STYLE, children=[
                html.H3("Order Fulfillment", style=SECTION_TITLE),
                dcc.Graph(id="chart-funnel", config={"displayModeBar": False}),
            ]),
            html.Div(style=CARD_STYLE, children=[
                html.H3("Warehouse Load", style=SECTION_TITLE),
                make_table("table-warehouse", ["Warehouse", "Total", "Pending", "Picking",
                                                "Packed", "Shipped", "Delayed", "Delay (min)"]),
            ]),
        ]),

        # Row 3: Fleet Map
        html.Details(open=False, style=CARD_STYLE, children=[
            html.Summary("Fleet Map — Live truck positions",
                         style={"cursor": "pointer", **SECTION_TITLE}),
            dcc.Graph(id="chart-map", config={"displayModeBar": False}),
        ]),

        # Row 4: ETA + Alerts
        html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px"}, children=[
            html.Div(style=CARD_STYLE, children=[
                html.H3("Fleet ETA Predictions", style=SECTION_TITLE),
                make_table("table-eta", ["Shipment", "Truck", "Stops Left", "Speed",
                                          "ETA (min)", "Status", "Confidence"]),
            ]),
            html.Div(style=CARD_STYLE, children=[
                html.H3("Delay Alerts", style=SECTION_TITLE),
                make_table("table-alerts", ["Source", "Origin", "Order", "Delay (min)",
                                             "Reason"]),
            ]),
        ]),

        # Row 5: Agent Actions
        html.Div(style=CARD_STYLE, children=[
            html.H3("AI Agent Actions", style=SECTION_TITLE),
            html.Div(id="agent-metrics", style={"display": "flex", "gap": "12px",
                                                  "marginBottom": "12px"}),
            make_table("table-actions", ["Agent", "Action", "Target", "Reasoning", "Detail"]),
        ]),

        # Row 6: Cascade Impact
        html.Div(style=CARD_STYLE, children=[
            html.H3("Cascade Impact", style=SECTION_TITLE),
            make_table("table-cascade", ["Warehouse", "Delay (min)", "Order", "Customer",
                                          "Priority", "Shipment", "Truck", "Destination"]),
        ]),

        # Footer
        html.Div(style={"textAlign": "center", "padding": "24px 0 12px 0"}, children=[
            html.A("Docs", href=RW_DOCS, target="_blank",
                   style={"color": TEXT_MUTED, "margin": "0 12px", "fontSize": "0.75rem",
                          "textDecoration": "none"}),
            html.A("GitHub", href=RW_GITHUB, target="_blank",
                   style={"color": TEXT_MUTED, "margin": "0 12px", "fontSize": "0.75rem",
                          "textDecoration": "none"}),
            html.A("Cloud", href=RW_CLOUD, target="_blank",
                   style={"color": TEXT_MUTED, "margin": "0 12px", "fontSize": "0.75rem",
                          "textDecoration": "none"}),
            html.P(["Powered by ",
                     html.A("RisingWave", href=RW_URL, target="_blank",
                            style={"color": BRAND_BLUE_LIGHT, "textDecoration": "none"}),
                     " Streaming Database"],
                    style={"color": TEXT_DIM, "fontSize": "0.6rem", "marginTop": "8px"}),
        ]),
    ]),
])

# ── Callbacks ────────────────────────────────────────────────────────────────

# Update refresh interval
@callback(Output("interval", "interval"), Input("refresh-dropdown", "value"))
def update_interval(val):
    return val


# Control buttons
@callback(
    Output("status-text", "children"),
    Input("btn-gen", "n_clicks"),
    Input("btn-agent", "n_clicks"),
    Input("btn-disrupt", "n_clicks"),
    Input("btn-reset", "n_clicks"),
    prevent_initial_call=True,
)
def handle_buttons(gen_clicks, agent_clicks, disrupt_clicks, reset_clicks):
    triggered = ctx.triggered_id
    if triggered == "btn-gen":
        if _gen_running:
            stop_generators()
            return "Generators stopped"
        else:
            start_generators()
            return "Generators started"
    elif triggered == "btn-agent":
        if _agent_running:
            stop_agents()
            return "Agents stopped"
        else:
            start_agents()
            return "Agents started"
    elif triggered == "btn-disrupt":
        from generators.scenarios import pick_random_scenario
        from scripts.trigger_disruption import trigger
        scenario = pick_random_scenario()
        affected = trigger(scenario["warehouse"], scenario["delay"], scenario["detail"])
        return f"{scenario['icon']} {scenario['name']} @ {scenario['warehouse']} — {affected} orders"
    elif triggered == "btn-reset":
        stop_generators()
        stop_agents()
        from scripts.reset import main as reset_main
        reset_main()
        return "All data reset"
    return ""


# Update button labels to reflect state
@callback(
    Output("btn-gen", "children"),
    Output("btn-agent", "children"),
    Input("interval", "n_intervals"),
)
def update_button_labels(_):
    gen_label = "Stop Generators" if _gen_running else "Start Generators"
    agent_label = "Stop Agents" if _agent_running else "Start Agents"
    return gen_label, agent_label


# Main data refresh — updates ALL panels on each interval tick
@callback(
    # KPI metrics
    Output("metric-total", "children"),
    Output("metric-shipped", "children"),
    Output("metric-delayed", "children"),
    Output("metric-actions", "children"),
    # Charts
    Output("chart-funnel", "figure"),
    Output("chart-map", "figure"),
    # Tables
    Output("table-warehouse", "data"),
    Output("table-eta", "data"),
    Output("table-alerts", "data"),
    Output("table-actions", "data"),
    Output("table-cascade", "data"),
    # Agent action metrics
    Output("agent-metrics", "children"),
    # Trigger
    Input("interval", "n_intervals"),
)
def refresh_dashboard(_):
    data = fetch_all()

    # KPI
    odf = pd.DataFrame(data["order_status"]) if data["order_status"] else pd.DataFrame()
    adf = pd.DataFrame(data["agent_counts"]) if data["agent_counts"] else pd.DataFrame()
    total = int(odf["cnt"].sum()) if not odf.empty else 0
    shipped = int(odf.loc[odf["current_status"] == "shipped", "cnt"].sum()) if not odf.empty else 0
    delayed = int(odf.loc[odf["current_status"] == "delay", "cnt"].sum()) if not odf.empty else 0
    agent_acts = int(adf["cnt"].sum()) if not adf.empty else 0

    # Order funnel chart
    if not odf.empty:
        cats = ["received", "picking", "packed", "shipped", "delay"]
        fdf = odf.copy()
        fdf["current_status"] = pd.Categorical(fdf["current_status"], categories=cats, ordered=True)
        fdf = fdf.sort_values("current_status").dropna(subset=["current_status"])
        funnel_fig = px.bar(fdf, x="current_status", y="cnt", color="current_status",
                            color_discrete_map=STAGE_COLORS,
                            labels={"current_status": "Status", "cnt": "Count"})
        funnel_fig.update_layout(showlegend=False)
        apply_rw_layout(funnel_fig, height=300)
    else:
        funnel_fig = go.Figure()
        apply_rw_layout(funnel_fig, height=300)

    # Fleet map
    if data.get("tracking"):
        tdf = pd.DataFrame(data["tracking"])
        tdf = tdf.dropna(subset=["lat", "lon"])
        tdf["lat"] = tdf["lat"].astype(float)
        tdf["lon"] = tdf["lon"].astype(float)
        tdf["speed_mph"] = tdf["speed_mph"].apply(lambda x: round(float(x), 1) if x else 0)
        tdf["status"] = tdf["speed_mph"].apply(
            lambda s: "On Time" if s >= 40 else ("Slight Delay" if s >= 25 else "Delayed")
        )
        color_map = {"On Time": BRAND_GREEN, "Slight Delay": WARNING, "Delayed": ERROR}
        map_fig = px.scatter_map(
            tdf, lat="lat", lon="lon", color="status", color_discrete_map=color_map,
            hover_name="truck_id",
            hover_data={"speed_mph": True, "remaining_stops": True,
                        "destination": True, "status": False, "lat": False, "lon": False},
            zoom=3, center={"lat": 37.5, "lon": -96},
        )
        map_fig.update_layout(
            height=350, margin=dict(t=0, b=0, l=0, r=0),
            paper_bgcolor="rgba(0,0,0,0)", map_style="carto-darkmatter",
            legend=dict(bgcolor="rgba(0,0,0,0.5)", font=dict(color="#fff", size=11),
                        orientation="h", yanchor="top", y=0.99, xanchor="left", x=0.01),
        )
        map_fig.update_traces(marker=dict(size=10))
    else:
        map_fig = go.Figure()
        map_fig.update_layout(height=350, margin=dict(t=0, b=0, l=0, r=0),
                              paper_bgcolor="rgba(0,0,0,0)")

    # Warehouse load table
    wh_data = []
    if data["warehouse_load"]:
        for r in data["warehouse_load"]:
            wh_data.append({
                "Warehouse": r["warehouse_id"], "Total": r["total_orders"],
                "Pending": r["pending"], "Picking": r["picking"], "Packed": r["packed"],
                "Shipped": r["shipped"], "Delayed": r["delayed"],
                "Delay (min)": r["total_delay_min"],
            })

    # ETA table
    eta_data = []
    if data["eta"]:
        for r in data["eta"]:
            eta_data.append({
                "Shipment": r["shipment_id"], "Truck": r["truck_id"],
                "Stops Left": r["remaining_stops"],
                "Speed": round(float(r["speed_mph"]), 1) if r["speed_mph"] else 0,
                "ETA (min)": round(float(r["eta_minutes"]), 1) if r["eta_minutes"] else "N/A",
                "Status": r["delay_status"], "Confidence": r["confidence"],
            })

    # Alerts table
    alert_data = []
    if data["alerts"]:
        for r in data["alerts"]:
            alert_data.append({
                "Source": r["alert_source"], "Origin": r["source_id"],
                "Order": r["affected_id"], "Delay (min)": r["delay_minutes"],
                "Reason": r["reason"],
            })

    # Actions table + metrics
    action_data = []
    reroutes = notifies = escalations = 0
    if data["actions"]:
        for r in data["actions"]:
            action_data.append({
                "Agent": r["agent_name"], "Action": r["action_type"],
                "Target": r["target_id"], "Reasoning": r["reasoning"],
                "Detail": r["detail"],
            })
            if r["action_type"] == "reroute": reroutes += 1
            elif r["action_type"] == "notify": notifies += 1
            elif r["action_type"] == "escalate": escalations += 1

    agent_metric_cards = [
        html.Div(style={**METRIC_STYLE, "padding": "8px 12px"}, children=[
            html.Div("Reroutes", style={"color": TEXT_MUTED, "fontSize": "0.65rem",
                                         "textTransform": "uppercase"}),
            html.Div(str(reroutes), style={"color": BRAND_GREEN, "fontSize": "1.4rem"}),
        ]),
        html.Div(style={**METRIC_STYLE, "padding": "8px 12px"}, children=[
            html.Div("Notifications", style={"color": TEXT_MUTED, "fontSize": "0.65rem",
                                              "textTransform": "uppercase"}),
            html.Div(str(notifies), style={"color": BRAND_BLUE_LIGHT, "fontSize": "1.4rem"}),
        ]),
        html.Div(style={**METRIC_STYLE, "padding": "8px 12px"}, children=[
            html.Div("Escalations", style={"color": TEXT_MUTED, "fontSize": "0.65rem",
                                            "textTransform": "uppercase"}),
            html.Div(str(escalations), style={"color": ERROR, "fontSize": "1.4rem"}),
        ]),
    ]

    # Cascade table
    cascade_data = []
    if data["cascade"]:
        for r in data["cascade"]:
            cascade_data.append({
                "Warehouse": r["warehouse_id"], "Delay (min)": r["warehouse_delay_min"],
                "Order": r["order_id"], "Customer": r["customer_name"],
                "Priority": r["priority"], "Shipment": r.get("shipment_id", ""),
                "Truck": r.get("truck_id", ""), "Destination": r.get("destination", ""),
            })

    return (
        str(total), str(shipped), str(delayed), str(agent_acts),
        funnel_fig, map_fig,
        wh_data, eta_data, alert_data, action_data, cascade_data,
        agent_metric_cards,
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8501)
