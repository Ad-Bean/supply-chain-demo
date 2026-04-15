"""ETA Prediction Agent — enriches basic speed-based ETAs with LLM reasoning.

Periodically checks shipments with low confidence scores and uses the LLM
to produce smarter ETAs considering time-of-day, route patterns, and
current conditions.
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
You are an ETA Prediction Agent for a supply chain control tower.

You receive shipment data including current speed, remaining stops, and a
basic ETA estimate. Your job is to provide a smarter, more nuanced prediction.

Consider:
- If speed is very low (<15 mph), the truck is likely in urban congestion —
  it may clear up, so don't over-penalize.
- If remaining stops are high (>6), small delays compound — factor in a
  realistic buffer.
- Time-of-day: afternoon shipments face more traffic than morning ones.
- If the basic ETA seems unreasonable (>200 min for a few stops), adjust it.

Respond with a JSON object (no markdown):
{
  "adjusted_eta_minutes": <number>,
  "confidence": <0.0-1.0>,
  "reasoning": "<1-2 sentences>"
}
"""


def get_low_confidence_shipments() -> list[dict]:
    """Find shipments with confidence < 0.8 that could benefit from smarter ETAs."""
    return query("""
        SELECT shipment_id, truck_id, remaining_stops, speed_mph,
               eta_minutes, delay_status, confidence, destination
        FROM mv_eta_predictions
        WHERE remaining_stops > 0 AND confidence < 0.8 AND eta_minutes IS NOT NULL
        ORDER BY confidence ASC
        LIMIT 5
    """)


def enrich_eta(shipment: dict):
    """Use LLM to produce a smarter ETA for a single shipment."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Shipment {shipment['shipment_id']} on {shipment['truck_id']}:\n"
                f"- Destination: {shipment['destination']}\n"
                f"- Current speed: {shipment['speed_mph']} mph\n"
                f"- Remaining stops: {shipment['remaining_stops']}\n"
                f"- Basic ETA: {float(shipment['eta_minutes'] or 0):.1f} min\n"
                f"- Current status: {shipment['delay_status']}\n"
                f"- Confidence: {shipment['confidence']}\n\n"
                f"Provide an adjusted ETA prediction."
            ),
        },
    ]

    try:
        response = chat(messages)
        content = response.content.strip()
        # Try to parse JSON from response
        if content.startswith("{"):
            result = json.loads(content)
        else:
            # Try extracting JSON from markdown code block
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(content[start:end])
            else:
                return

        # Log the enriched prediction as an agent action
        execute(
            """INSERT INTO agent_actions (action_id, agent_name, action_type,
               target_id, reasoning, detail)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (
                f"ACT-{uuid.uuid4().hex[:8].upper()}",
                "eta_agent",
                "predict",
                shipment["shipment_id"],
                result.get("reasoning", "ETA adjustment"),
                f"Adjusted ETA: {result.get('adjusted_eta_minutes', '?')}min "
                f"(confidence: {result.get('confidence', '?')})",
            ),
        )

        console.print(Panel(
            f"Shipment: {shipment['shipment_id']}\n"
            f"  Basic ETA: {shipment['eta_minutes']:.1f}min → "
            f"Adjusted: {result.get('adjusted_eta_minutes', '?')}min\n"
            f"  Confidence: {shipment['confidence']} → {result.get('confidence', '?')}\n"
            f"  Reasoning: {result.get('reasoning', 'N/A')}",
            title="ETA Agent — Prediction",
            border_style="blue",
        ))

    except Exception as e:
        console.print(f"[red]ETA Agent error: {e}[/]")


def run(poll_interval: float = 15.0, stop_event=None):
    """Poll for low-confidence shipments and enrich their ETAs."""
    console.print("[bold]ETA Prediction Agent started.[/]\n")

    while not (stop_event and stop_event.is_set()):
        try:
            shipments = get_low_confidence_shipments()
            if shipments:
                # Pick the lowest confidence one
                enrich_eta(shipments[0])
        except Exception as e:
            console.print(f"[red]ETA Agent error: {e}[/]")
        if stop_event:
            stop_event.wait(poll_interval)
        else:
            time.sleep(poll_interval)


if __name__ == "__main__":
    run()
