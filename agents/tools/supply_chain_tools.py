"""Tools that AI agents can call to query RisingWave and take actions.

Each function is registered as an OpenAI-compatible tool for the LLM.
"""

import json
import uuid

from db import query, execute

# -- Tool definitions (OpenAI function-calling format) --

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "query_cascade_impact",
            "description": (
                "Get all orders, shipments, and trucks affected by a warehouse delay. "
                "Returns customer names, priorities, and downstream shipment info."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "warehouse_id": {
                        "type": "string",
                        "description": "The warehouse ID experiencing the delay, e.g. WH-03",
                    }
                },
                "required": ["warehouse_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_warehouse_load",
            "description": (
                "Get current processing load for all warehouses or a specific one. "
                "Shows pending, picking, packed, shipped, delayed counts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "warehouse_id": {
                        "type": "string",
                        "description": "Optional: specific warehouse ID. Omit for all.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_delay_alerts",
            "description": "Get all current active delay alerts from warehouses and shipments.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_eta_predictions",
            "description": (
                "Get ETA predictions for all active shipments. "
                "Includes delay_status, confidence score, and estimated minutes."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reroute_order",
            "description": (
                "Reroute an order from its current warehouse to a different warehouse. "
                "Use when the current warehouse is delayed and another has capacity."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The order to reroute"},
                    "new_warehouse_id": {"type": "string", "description": "Target warehouse ID"},
                    "reason": {"type": "string", "description": "Why this reroute is needed"},
                },
                "required": ["order_id", "new_warehouse_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notify_customer",
            "description": (
                "Send a delay notification to a customer. "
                "Provide customer-friendly message about their order status."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "The affected order"},
                    "message": {"type": "string", "description": "Customer-facing notification message"},
                },
                "required": ["order_id", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escalate_alert",
            "description": "Escalate a critical situation to human operators with a summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Escalation summary for ops team"},
                    "severity": {
                        "type": "string",
                        "enum": ["medium", "high", "critical"],
                        "description": "Severity level",
                    },
                },
                "required": ["summary", "severity"],
            },
        },
    },
]


# -- Tool implementations --

def query_cascade_impact(warehouse_id: str) -> str:
    rows = query(
        "SELECT * FROM mv_cascade_impact WHERE warehouse_id = %s", (warehouse_id,)
    )
    return json.dumps(rows, default=str)


def query_warehouse_load(warehouse_id: str | None = None) -> str:
    if warehouse_id:
        rows = query(
            "SELECT * FROM mv_warehouse_load WHERE warehouse_id = %s", (warehouse_id,)
        )
    else:
        rows = query("SELECT * FROM mv_warehouse_load")
    return json.dumps(rows, default=str)


def query_delay_alerts() -> str:
    rows = query("SELECT * FROM mv_delay_alerts ORDER BY created_at DESC LIMIT 20")
    return json.dumps(rows, default=str)


def query_eta_predictions() -> str:
    rows = query("SELECT * FROM mv_eta_predictions ORDER BY eta_minutes DESC LIMIT 20")
    return json.dumps(rows, default=str)


def reroute_order(order_id: str, new_warehouse_id: str, reason: str) -> str:
    # Log the agent action
    action_id = f"ACT-{uuid.uuid4().hex[:8].upper()}"
    execute(
        """INSERT INTO agent_actions (action_id, agent_name, action_type,
           target_id, reasoning, detail)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (action_id, "disruption_agent", "reroute", order_id, reason,
         f"Rerouted to {new_warehouse_id}"),
    )
    # Insert a new warehouse event to restart processing at new warehouse
    execute(
        """INSERT INTO warehouse_events (event_id, order_id, warehouse_id,
           event_type, delay_minutes, detail)
           VALUES (%s, %s, %s, 'received', 0, %s)""",
        (f"WE-{uuid.uuid4().hex[:8].upper()}", order_id, new_warehouse_id,
         f"Rerouted by AI agent: {reason}"),
    )
    return json.dumps({"status": "ok", "action_id": action_id,
                        "order_id": order_id, "new_warehouse": new_warehouse_id})


def notify_customer(order_id: str, message: str) -> str:
    action_id = f"ACT-{uuid.uuid4().hex[:8].upper()}"
    execute(
        """INSERT INTO agent_actions (action_id, agent_name, action_type,
           target_id, reasoning, detail)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (action_id, "disruption_agent", "notify", order_id,
         "Customer delay notification", message),
    )
    return json.dumps({"status": "sent", "action_id": action_id,
                        "order_id": order_id, "message": message})


def escalate_alert(summary: str, severity: str) -> str:
    action_id = f"ACT-{uuid.uuid4().hex[:8].upper()}"
    execute(
        """INSERT INTO agent_actions (action_id, agent_name, action_type,
           target_id, reasoning, detail)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (action_id, "disruption_agent", "escalate", "ops_team",
         summary, f"Severity: {severity}"),
    )
    return json.dumps({"status": "escalated", "action_id": action_id,
                        "severity": severity})


# Map function name → callable
TOOL_DISPATCH = {
    "query_cascade_impact": lambda **kw: query_cascade_impact(**kw),
    "query_warehouse_load": lambda **kw: query_warehouse_load(**kw),
    "query_delay_alerts": lambda **kw: query_delay_alerts(),
    "query_eta_predictions": lambda **kw: query_eta_predictions(),
    "reroute_order": lambda **kw: reroute_order(**kw),
    "notify_customer": lambda **kw: notify_customer(**kw),
    "escalate_alert": lambda **kw: escalate_alert(**kw),
}
