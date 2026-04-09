# Supply Chain Control Tower Demo

**End-to-end supply chain monitoring + AI-powered disruption response**, built on [RisingWave](https://risingwave.com) streaming database.

## The Story

```
Orders come in → Warehouse processes them → Shipments go out → Trucks deliver
                              ↓
                         RisingWave
                     (6 materialized views)
                              ↓
                   AI Agent detects disruption
                   → reroutes orders
                   → notifies customers
                   → escalates to ops
```

**The wow moment:** One warehouse disruption cascades into delayed shipments, updated ETAs, and triggered alerts — then an AI agent autonomously resolves it in seconds.

## Architecture

```
Data Generators          RisingWave Cloud              AI Agent
─────────────────      ──────────────────────      ─────────────────
orders_gen.py     →    orders table                 disruption_agent.py
warehouse_gen.py  →    warehouse_events table   ←── queries MVs
shipment_gen.py   →    shipments table              calls tools:
gps_gen.py        →    gps_pings table              - reroute_order
                       ↓                            - notify_customer
                       6 materialized views          - escalate_alert
                       (auto-updating)               ↓
                       ↓                            agent_actions table
                       Grafana dashboard
```

## Quick Start

```bash
# 1. Setup
cd supply-chain-demo
python3 -m venv .venv
.venv/bin/pip install psycopg2-binary python-dotenv openai rich

# 2. Configure
cp .env.example .env
# Edit .env with your RisingWave and OpenRouter credentials

# 3. Create schema
PYTHONPATH=. .venv/bin/python3 scripts/setup_schema.py

# 4. Run the full demo (one command)
PYTHONPATH=. .venv/bin/python3 scripts/run_demo.py
```

### Or run components separately

```bash
# Terminal 1: Data generators
PYTHONPATH=. .venv/bin/python3 scripts/run_generators.py

# Terminal 2: AI agent
PYTHONPATH=. .venv/bin/python3 scripts/run_agent.py

# Terminal 3: Trigger disruption
PYTHONPATH=. .venv/bin/python3 scripts/trigger_disruption.py WH-03 45

# Terminal 4: Dashboard
PYTHONPATH=. .venv/bin/python3 scripts/dashboard_query.py

# Reset for fresh run
PYTHONPATH=. .venv/bin/python3 scripts/reset.py
```

## What the AI Agent Does

When a warehouse delay is detected (via `mv_delay_alerts`):

1. **PERCEIVE** — Queries `mv_cascade_impact` and `mv_warehouse_load` to understand the full blast radius
2. **REASON** — LLM analyzes severity: how many orders affected? VIP customers? Available capacity elsewhere?
3. **ACT** — Takes autonomous actions:
   - **Reroute** VIP/express orders to less-loaded warehouses
   - **Notify** affected customers with personalized messages
   - **Escalate** to ops team if critical (>5 orders or VIP impacted)
4. **OBSERVE** — Actions write back to RisingWave; MVs update in seconds

## Key Files

```
supply-chain-demo/
├── config.py                          # Shared config from .env
├── db.py                              # RisingWave connection helper
├── sql/
│   ├── 01-tables.sql                  # 5 source tables
│   └── 02-materialized-views.sql      # 6 streaming MVs
├── generators/
│   ├── seed_data.py                   # Warehouses, products, customers, trucks
│   ├── order_gen.py                   # Simulates incoming orders
│   ├── warehouse_gen.py               # Processes orders through pick/pack/ship
│   ├── shipment_gen.py                # Creates shipments for shipped orders
│   └── gps_gen.py                     # Emits truck GPS pings
├── agents/
│   ├── llm.py                         # OpenRouter client with retry
│   ├── disruption_agent.py            # Main AI agent (perceive→reason→act)
│   └── tools/
│       └── supply_chain_tools.py      # 7 tools the agent can call
├── scripts/
│   ├── setup_schema.py                # Apply DDL to RisingWave
│   ├── run_generators.py              # Run all generators concurrently
│   ├── run_agent.py                   # Run disruption agent
│   ├── run_demo.py                    # Full orchestrated demo
│   ├── trigger_disruption.py          # Inject chaos
│   ├── reset.py                       # Clear all data
│   └── dashboard_query.py             # CLI dashboard
└── grafana/
    ├── datasource.yml                 # Grafana → RisingWave config
    └── dashboard.json                 # 6-panel dashboard
```

## Grafana Setup

1. Add RisingWave as a PostgreSQL datasource using connection details from `.env`
2. Import `grafana/dashboard.json`
3. Set refresh to 5s

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `RW_HOST` | RisingWave host | `localhost` |
| `RW_PORT` | RisingWave port | `4566` |
| `RW_USER` | Database user | `root` |
| `RW_PASSWORD` | Database password | |
| `RW_DATABASE` | Database name | `dev` |
| `RW_SSLMODE` | SSL mode | `prefer` |
| `OPENROUTER_API_KEY` | OpenRouter API key | |
| `OPENROUTER_MODEL` | LLM model | `google/gemma-4-31b-it:free` |
| `GENERATOR_SPEED` | Speed multiplier | `1.0` |
| `NUM_TRUCKS` | Number of trucks | `10` |
| `NUM_WAREHOUSES` | Number of warehouses | `3` |
