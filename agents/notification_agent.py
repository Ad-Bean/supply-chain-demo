"""Customer Notification Agent — generates context-aware delay messages.

Watches for new delay alerts and crafts personalized customer notifications
based on order priority, delay severity, and whether the customer has
been previously notified.
"""

import json
import time
import uuid

from rich.console import Console
from rich.panel import Panel

from agents.llm import chat
from db import query, execute

console = Console()

SYSTEM_PROMPT = """\
You are a Customer Notification Agent for a supply chain company.

When an order is delayed, you craft a short, empathetic notification message
for the customer. Tailor the tone based on priority:

- VIP: Apologetic, proactive, mention what you're doing to fix it.
  Offer a gesture (e.g., "we'll prioritize your shipment").
- Express: Professional, acknowledge urgency, provide clear ETA update.
- Standard: Friendly, brief, reassuring. No over-promising.

Rules:
- Keep messages under 50 words.
- Don't use generic corporate speak. Be human.
- Include the customer's first name.
- If delay > 45 min, acknowledge it's significant.
- Never blame the customer or other departments.

Respond with JSON (no markdown):
{
  "message": "<the customer-facing message>",
  "channel": "sms" | "email" | "push"
}
"""


def get_unnotified_delays() -> list[dict]:
    """Find delayed orders that haven't been notified yet."""
    return query("""
        SELECT ci.order_id, ci.customer_name, ci.priority,
               ci.warehouse_id, ci.warehouse_delay_min
        FROM mv_cascade_impact ci
        WHERE ci.order_id NOT IN (
            SELECT target_id FROM agent_actions
            WHERE action_type IN ('notify', 'resolve')
        )
        ORDER BY
            CASE ci.priority WHEN 'vip' THEN 1 WHEN 'express' THEN 2 ELSE 3 END,
            ci.warehouse_delay_min DESC
        LIMIT 3
    """)


def notify_customer(order: dict):
    """Use LLM to generate and send a personalized notification."""
    first_name = order["customer_name"].split()[0]

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Customer: {order['customer_name']} (priority: {order['priority']})\n"
                f"Order: {order['order_id']}\n"
                f"Warehouse: {order['warehouse_id']}\n"
                f"Delay: {order['warehouse_delay_min']} minutes\n\n"
                f"Generate a notification for {first_name}."
            ),
        },
    ]

    try:
        response = chat(messages)
        content = response.content.strip()

        # Parse JSON
        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            result = json.loads(content[start:end])
        else:
            result = {"message": content, "channel": "sms"}

        msg = result.get("message", content)
        channel = result.get("channel", "sms")

        execute(
            """INSERT INTO agent_actions (action_id, agent_name, action_type,
               target_id, reasoning, detail)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                f"ACT-{uuid.uuid4().hex[:8].upper()}",
                "notification_agent",
                "notify",
                order["order_id"],
                f"{order['priority'].upper()} customer notification via {channel}",
                msg,
            ),
        )

        console.print(Panel(
            f"To: {order['customer_name']} ({order['priority']})\n"
            f"Channel: {channel}\n"
            f"Message: {msg}",
            title="Notification Agent",
            border_style="magenta",
        ))

    except Exception as e:
        console.print(f"[red]Notification Agent error: {e}[/]")


def run(poll_interval: float = 10.0, stop_event=None):
    """Poll for unnotified delays and send personalized messages."""
    console.print("[bold]Customer Notification Agent started.[/]\n")

    while not (stop_event and stop_event.is_set()):
        try:
            orders = get_unnotified_delays()
            for order in orders:
                notify_customer(order)
        except Exception as e:
            console.print(f"[red]Notification Agent error: {e}[/]")
        time.sleep(poll_interval)


if __name__ == "__main__":
    run()
