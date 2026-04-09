"""Quick dashboard — query all materialized views and print a summary.
Useful for verifying the system is working before Grafana is set up."""

from rich.console import Console
from rich.table import Table

from db import query

console = Console()


def show():
    # Order status
    rows = query("SELECT current_status, COUNT(*) AS cnt FROM mv_order_status GROUP BY current_status ORDER BY cnt DESC")
    t = Table(title="Order Status Funnel")
    t.add_column("Status")
    t.add_column("Count", justify="right")
    for r in rows:
        t.add_row(str(r["current_status"]), str(r["cnt"]))
    console.print(t)

    # Warehouse load
    rows = query("SELECT * FROM mv_warehouse_load")
    t = Table(title="Warehouse Load")
    t.add_column("Warehouse")
    t.add_column("Total", justify="right")
    t.add_column("Pending", justify="right")
    t.add_column("Picking", justify="right")
    t.add_column("Packed", justify="right")
    t.add_column("Shipped", justify="right")
    t.add_column("Delayed", justify="right", style="red")
    t.add_column("Delay Min", justify="right", style="red")
    for r in rows:
        t.add_row(
            str(r["warehouse_id"]),
            str(r["total_orders"]),
            str(r["pending"]),
            str(r["picking"]),
            str(r["packed"]),
            str(r["shipped"]),
            str(r["delayed"]),
            str(r["total_delay_min"]),
        )
    console.print(t)

    # ETA predictions
    rows = query("SELECT * FROM mv_eta_predictions WHERE delay_status != 'on_time' ORDER BY eta_minutes DESC LIMIT 10")
    if rows:
        t = Table(title="Delayed Shipments (ETA)")
        t.add_column("Shipment")
        t.add_column("Truck")
        t.add_column("ETA (min)", justify="right")
        t.add_column("Status")
        t.add_column("Confidence", justify="right")
        for r in rows:
            t.add_row(
                str(r["shipment_id"]),
                str(r["truck_id"]),
                f"{r['eta_minutes']:.1f}" if r["eta_minutes"] else "N/A",
                str(r["delay_status"]),
                f"{r['confidence']:.2f}" if r["confidence"] else "N/A",
            )
        console.print(t)

    # Agent actions
    rows = query("SELECT * FROM agent_actions ORDER BY created_at DESC LIMIT 10")
    if rows:
        t = Table(title="Recent Agent Actions")
        t.add_column("Action")
        t.add_column("Agent")
        t.add_column("Type")
        t.add_column("Target")
        t.add_column("Reasoning")
        for r in rows:
            t.add_row(
                str(r["action_id"]),
                str(r["agent_name"]),
                str(r["action_type"]),
                str(r["target_id"]),
                str(r["reasoning"])[:60],
            )
        console.print(t)
    else:
        console.print("[dim]No agent actions yet.[/]")


if __name__ == "__main__":
    show()
