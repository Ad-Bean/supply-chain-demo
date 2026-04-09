"""One-command demo orchestrator.

Runs the full supply chain demo end-to-end:
1. Reset data
2. Start generators (background threads)
3. Start agent (background thread)
4. Wait for pipeline to fill
5. Trigger disruption
6. Show dashboard as agent responds
"""

import threading
import time
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from scripts.reset import main as reset_data
from generators.order_gen import run as run_orders
from generators.warehouse_gen import run as run_warehouse
from generators.shipment_gen import run as run_shipments
from generators.gps_gen import run as run_gps
from agents.disruption_agent import run as run_agent
from scripts.trigger_disruption import trigger
from db import query

console = Console()


def build_dashboard() -> Table:
    """Build a summary table from MVs."""
    grid = Table(title="Supply Chain Control Tower", expand=True)
    grid.add_column("Metric", style="bold")
    grid.add_column("Value", justify="right")

    # Order counts
    try:
        rows = query("SELECT current_status, COUNT(*) AS cnt FROM mv_order_status GROUP BY current_status ORDER BY cnt DESC")
        for r in rows:
            grid.add_row(f"Orders: {r['current_status']}", str(r["cnt"]))
    except Exception:
        grid.add_row("Orders", "loading...")

    # Warehouse delays
    try:
        rows = query("SELECT warehouse_id, delayed, total_delay_min FROM mv_warehouse_load WHERE delayed > 0")
        for r in rows:
            grid.add_row(
                f"[red]Delayed @ {r['warehouse_id']}[/]",
                f"[red]{r['delayed']} orders, {r['total_delay_min']}min[/]"
            )
    except Exception:
        pass

    # Agent actions
    try:
        rows = query("SELECT action_type, COUNT(*) AS cnt FROM agent_actions GROUP BY action_type")
        for r in rows:
            style = "green" if r["action_type"] == "reroute" else "yellow"
            grid.add_row(f"[{style}]Agent: {r['action_type']}[/]", f"[{style}]{r['cnt']}[/]")
    except Exception:
        pass

    return grid


def main():
    target_warehouse = sys.argv[1] if len(sys.argv) > 1 else "WH-03"
    delay_minutes = int(sys.argv[2]) if len(sys.argv) > 2 else 45
    fill_time = int(sys.argv[3]) if len(sys.argv) > 3 else 30

    # Step 1: Reset
    console.print(Panel("[bold]Step 1/5: Resetting data...[/]", border_style="blue"))
    reset_data()

    # Step 2: Start generators
    console.print(Panel("[bold]Step 2/5: Starting data generators...[/]", border_style="blue"))
    for target, kwargs in [
        (run_orders, {"interval": 1.5}),
        (run_warehouse, {"interval": 2.0}),
        (run_shipments, {"interval": 1.5}),
        (run_gps, {"interval": 3.0}),
    ]:
        threading.Thread(target=target, kwargs=kwargs, daemon=True).start()

    # Step 3: Start agent
    console.print(Panel("[bold]Step 3/5: Starting AI disruption agent...[/]", border_style="blue"))
    threading.Thread(target=run_agent, kwargs={"poll_interval": 5.0}, daemon=True).start()

    # Step 4: Let pipeline fill
    console.print(Panel(
        f"[bold]Step 4/5: Filling pipeline for {fill_time}s...[/]\n"
        f"  Orders flowing → warehouse processing → shipments → GPS",
        border_style="blue",
    ))
    for i in range(fill_time):
        time.sleep(1)
        if (i + 1) % 10 == 0:
            try:
                cnt = query("SELECT COUNT(*) AS c FROM orders")[0]["c"]
                console.print(f"  [{i+1}s] {cnt} orders in system")
            except Exception:
                pass

    # Step 5: Trigger disruption
    console.print(Panel(
        f"[bold red]Step 5/5: TRIGGERING DISRUPTION @ {target_warehouse}![/]\n"
        f"  Delay: {delay_minutes} minutes\n"
        f"  Watch the agent respond below...",
        border_style="red",
    ))
    trigger(target_warehouse, delay_minutes)

    # Monitor dashboard
    console.print("\n[bold]Monitoring... (Ctrl+C to stop)[/]\n")
    try:
        while True:
            time.sleep(10)
            console.print(build_dashboard())
            console.print()
    except KeyboardInterrupt:
        console.print("\n[bold]Demo ended.[/]")


if __name__ == "__main__":
    main()
