"""Disruption Response Agent — the star of the demo.

Monitors mv_delay_alerts via polling. When a warehouse delay is detected:
1. PERCEIVE  — queries cascade impact and warehouse loads directly
2. REASON    — LLM analyzes severity and decides actions
3. ACT       — LLM calls action tools (reroute, notify, escalate)
4. OBSERVE   — confirms resolution via dashboard
"""

import json
import time

from rich.console import Console
from rich.panel import Panel

from agents.llm import chat
from agents.tools.supply_chain_tools import (
    TOOL_DEFINITIONS, TOOL_DISPATCH,
    query_cascade_impact, query_warehouse_load, query_delay_alerts,
)
from db import query

console = Console()

SYSTEM_PROMPT = """\
You are a Supply Chain Disruption Response Agent. You monitor a real-time supply chain
control tower powered by RisingWave streaming database.

You have already been given the cascade impact data and warehouse load data.
Your job is to **handle and resolve** disruptions autonomously:

1. REROUTE VIP/express orders to less-loaded warehouses when the current warehouse is delayed.
2. RESOLVE delayed orders by re-queuing them — either at an alternate warehouse or at the
   same warehouse once conditions allow. Always resolve orders after rerouting them.
3. NOTIFY affected customers with clear, friendly messages about the delay and resolution.
4. ESCALATE to human operators only if the situation is critical (>5 orders affected or VIP impacted).

Decision rules:
- VIP/express orders: reroute to the least-loaded warehouse, then resolve.
- Standard orders with delay < 30 min: resolve at the same warehouse (delay will clear).
- Standard orders with delay >= 30 min: reroute to a less-loaded warehouse, then resolve.
- Always notify customers when their order is affected.

Available warehouses: WH-01 (East Coast), WH-02 (Midwest), WH-03 (West Coast).

Take action now. Handle every affected order — reroute, resolve, and notify.
"""

# Only action tools (smaller payload)
ACTION_TOOLS = [t for t in TOOL_DEFINITIONS if t["function"]["name"] in (
    "reroute_order", "resolve_order", "notify_customer", "escalate_alert"
)]


def get_new_alerts(seen_ids: set) -> list[dict]:
    """Poll for delay alerts not yet processed.

    Checks both the in-memory seen set AND the agent_actions table
    to avoid re-processing orders that were already handled (even
    across agent restarts).
    """
    alerts = query("""
        SELECT alert_source, source_id, affected_id, delay_minutes, reason, created_at
        FROM mv_delay_alerts
        WHERE alert_source = 'warehouse'
          AND affected_id NOT IN (
              SELECT target_id FROM agent_actions
              WHERE action_type IN ('reroute', 'resolve')
          )
        ORDER BY created_at DESC
        LIMIT 10
    """)
    return [a for a in alerts if a["affected_id"] not in seen_ids]


def run_agent_loop(alert: dict) -> str:
    """Run the full agent loop for a single disruption alert."""

    # === PHASE 1: PERCEIVE — gather data directly (no LLM needed) ===
    console.print(Panel(
        f"[bold red]ALERT[/] Warehouse delay detected!\n"
        f"  Warehouse: {alert['source_id']}\n"
        f"  Order: {alert['affected_id']}\n"
        f"  Delay: {alert['delay_minutes']} min\n"
        f"  Reason: {alert['reason']}",
        title="Disruption Agent — PERCEIVE",
        border_style="red",
    ))

    cascade = query_cascade_impact(alert["source_id"])
    wh_load = query_warehouse_load()

    console.print(Panel(
        f"Cascade impact:\n{cascade[:500]}\n\nWarehouse loads:\n{wh_load[:500]}",
        title="Disruption Agent — DATA GATHERED",
        border_style="yellow",
    ))

    # === PHASE 2: REASON + ACT — send data to LLM with action tools ===
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"DISRUPTION ALERT at warehouse {alert['source_id']}:\n"
                f"- Delay: {alert['delay_minutes']} minutes\n"
                f"- Reason: {alert['reason']}\n\n"
                f"CASCADE IMPACT (all affected orders):\n{cascade}\n\n"
                f"WAREHOUSE LOADS (capacity check):\n{wh_load}\n\n"
                f"Take appropriate actions: reroute VIP/express orders to less-loaded "
                f"warehouses, notify customers, and escalate if needed."
            ),
        },
    ]

    actions_taken = []
    response = None
    for turn in range(6):
        try:
            response = chat(messages, tools=ACTION_TOOLS)
        except RuntimeError:
            console.print("[dim]  (rate limit on summary — actions already completed)[/]")
            break

        if response.content:
            console.print(Panel(
                response.content,
                title=f"Agent — {'REASON' if turn == 0 else 'CONTINUE'} (turn {turn + 1})",
                border_style="cyan",
            ))

        if not response.tool_calls:
            break

        messages.append(response)
        for tc in response.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments) if tc.function.arguments else {}

            console.print(f"  [yellow]-> calling[/] {fn_name}({json.dumps(fn_args)})")

            if fn_name in TOOL_DISPATCH:
                result = TOOL_DISPATCH[fn_name](**fn_args)
            else:
                result = json.dumps({"error": f"Unknown tool: {fn_name}"})

            actions_taken.append(f"{fn_name}({fn_args.get('order_id', fn_args.get('summary', '')[:40])})")
            console.print(f"  [green]<- result[/] {result[:200]}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    summary = response.content if response and response.content else None
    if not summary:
        summary = f"Completed {len(actions_taken)} actions:\n" + "\n".join(f"  - {a}" for a in actions_taken)
    console.print(Panel(summary, title="Agent — RESOLUTION", border_style="green"))
    return summary


def run(poll_interval: float = 5.0, stop_event=None):
    """Main polling loop — watches for new delay alerts."""
    seen: set[str] = set()
    console.print("[bold]Disruption Agent started. Watching for delay alerts...[/]\n")

    while not (stop_event and stop_event.is_set()):
        try:
            alerts = get_new_alerts(seen)
            for alert in alerts:
                seen.add(alert["affected_id"])
                run_agent_loop(alert)
                console.print()
        except Exception as e:
            console.print(f"[red]Error: {e}[/]")
        time.sleep(poll_interval)


if __name__ == "__main__":
    run()
