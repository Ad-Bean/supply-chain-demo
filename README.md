# Supply Chain Control Tower Demo

**End-to-end supply chain monitoring + AI-powered disruption response**, built on [RisingWave](https://risingwave.com) streaming database.

## The Story

```
Orders come in → Warehouse processes them → Shipments go out → Trucks deliver
                              ↓
                         RisingWave
                     (6 materialized views)
                              ↓
                  GPS ping drops → ETA updates → alert fires
                              ↓
                      3 AI Agents respond autonomously
                      → reroute orders
                      → predict ETAs
                      → notify customers
```

**The wow moment:** One warehouse disruption cascades into delayed shipments, updated ETAs, and triggered alerts — then AI agents autonomously resolve it in seconds. All powered by streaming SQL, no application glue code.

## Live Demo

The entire demo runs from a single browser tab:

```bash
PYTHONPATH=. .venv/bin/streamlit run web/app.py
```

1. Toggle **Data Generators** ON — orders, warehouse events, shipments, and GPS pings start flowing
2. Toggle **AI Agents** ON — 3 agents start watching the same MVs that power the dashboard
3. Wait ~20 seconds for the pipeline to fill
4. Select a disruption scenario and click **Trigger Disruption**
5. Watch the cascade: warehouse delay → ETA spike → delay alert → agent reroutes/notifies

### Dashboard Sections

| Section | What it shows | Key MVs |
|---------|--------------|---------|
| **Unified Inventory View** | Order funnel, warehouse load by stage, cascade impact of delays | `mv_order_status`, `mv_warehouse_load`, `mv_cascade_impact` |
| **Freight Intelligence** | Fleet map, ETA predictions with compounding delay model, unified delay alerts (warehouse + shipment) | `mv_shipment_tracking`, `mv_eta_predictions`, `mv_delay_alerts` |
| **AI-Native Supply Chain** | Autonomous agent actions: reroutes, resolutions, notifications, escalations | `agent_actions` table |

### What to highlight in a demo

- **Streaming SQL, not application code.** Every panel is backed by a materialized view that updates incrementally — no batch jobs, no ETL pipelines.
- **MV chaining.** `mv_delay_alerts` reads from `mv_eta_predictions`, which reads from `gps_pings` + `shipments`. A single GPS ping change propagates through the entire DAG automatically.
- **Two types of delays.** Normal delays (equipment issues, scanner failures, mislabeled bins) happen randomly during warehouse processing. Disruption delays (power outage, severe weather, fire alarm) are triggered manually to simulate real-world chaos.
- **AI agents consume the same MVs.** The disruption agent queries `mv_delay_alerts` and `mv_cascade_impact` — the exact same views the dashboard reads. No separate data pipeline for AI.
- **Toggle Show SQL** to reveal the actual MV definitions behind each panel.

## Architecture

```
Data Generators          RisingWave Cloud              AI Agents
─────────────────      ──────────────────────      ─────────────────
order_gen.py      →    orders table                 disruption_agent.py
warehouse_gen.py  →    warehouse_events table   ←── queries MVs, takes action
shipment_gen.py   →    shipments table              eta_agent.py
gps_gen.py        →    gps_pings table              notification_agent.py
                       ↓                                ↓
                       6 materialized views          agent_actions table
                       (incrementally updated)          ↓
                       ↓                            Streamlit dashboard
                       Streamlit dashboard
```

### Materialized View DAG

```
gps_pings ──→ mv_shipment_tracking
         └──→ mv_eta_predictions ──→ mv_delay_alerts ──→ AI agents
warehouse_events ──→ mv_delay_alerts
                └──→ mv_warehouse_load
                └──→ mv_cascade_impact
orders ──→ mv_order_status
```

## AI Agents

| Agent | What it does | Poll interval |
|-------|-------------|---------------|
| **Disruption Response** | Detects warehouse delays, queries cascade impact, reroutes VIP/express orders, resolves standard orders, escalates critical situations | 5s |
| **ETA Prediction** | Enriches low-confidence ETAs using LLM reasoning about traffic patterns, time-of-day, and route conditions | 15s |
| **Customer Notification** | Crafts personalized delay messages based on customer priority (VIP/express/standard) and delay severity | 10s |

## Delay Types

### Normal delays (random, during warehouse processing)
10% chance during picking or packing. Reasons vary: equipment malfunction, scanner failure, forklift battery, mislabeled bin, quality check hold, pallet wrapping machine offline, shift handover gap, barcode unreadable, overweight repack, dock door fault.

### Disruption delays (manually triggered via dashboard)
8 realistic scenarios with randomized parameters:

| Scenario | Delay Range | Description |
|----------|-------------|-------------|
| Equipment Failure | 30-60 min | Conveyor belt malfunction halts picking line |
| Power Outage | 45-90 min | Grid failure knocks out operations |
| Labor Shortage | 20-45 min | 60% staff call-outs reduce capacity |
| Inventory Miscount | 25-50 min | Cycle count discrepancy triggers audit |
| Severe Weather | 30-75 min | Tornado warning forces shelter-in-place |
| WMS System Outage | 20-40 min | Warehouse Management System crash |
| Fire Alarm | 40-90 min | Mandatory evacuation |
| Shipping Dock Backup | 25-55 min | Truck scheduling error creates congestion |

### Shipment delays (derived from GPS speed)
Computed in `mv_eta_predictions` — when truck speed drops below 25 mph, the shipment is flagged as delayed. `mv_delay_alerts` derives a human-readable reason: traffic slowdown, severe congestion, or vehicle stopped.

## Quick Start

### Local Development

```bash
# 1. Clone and setup
cd supply-chain-demo
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env with your RisingWave Cloud and OpenRouter credentials

# 3. Create schema (once)
PYTHONPATH=. .venv/bin/python3 scripts/setup_schema.py

# 4. Run
PYTHONPATH=. .venv/bin/streamlit run web/app.py
```

### Streamlit Cloud Deployment

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your repo, set **Main file path** to `web/app.py`
4. In **Settings > Secrets**, paste your credentials:
   ```toml
   RW_HOST = "your-risingwave-host.risingwave.cloud"
   RW_PORT = "4566"
   RW_USER = "your-user"
   RW_PASSWORD = "your-password"
   RW_DATABASE = "dev"
   RW_SSLMODE = "require"
   OPENROUTER_API_KEY = "your-openrouter-key"
   OPENROUTER_MODEL = "your-chosen-model"
   ```
5. Deploy

### CLI Mode (no browser)

```bash
# Terminal 1: Data generators
PYTHONPATH=. .venv/bin/python3 scripts/run_generators.py

# Terminal 2: AI agents
PYTHONPATH=. .venv/bin/python3 scripts/run_agent.py

# Terminal 3: Trigger disruption
PYTHONPATH=. .venv/bin/python3 scripts/trigger_disruption.py WH-03 45

# Terminal 4: Dashboard
PYTHONPATH=. .venv/bin/python3 scripts/dashboard_query.py
```

## Project Structure

```
supply-chain-demo/
├── .streamlit/
│   └── config.toml                    # Streamlit theme (RisingWave dark)
├── web/
│   ├── app.py                         # Streamlit dashboard (main entry point)
│   ├── panels.py                      # Dashboard panel render functions
│   ├── theme.py                       # RisingWave brand tokens + Plotly theming
│   └── sql_docs.py                    # MV SQL definitions for Show SQL mode
├── agents/
│   ├── disruption_agent.py            # Disruption response (reroute/escalate)
│   ├── eta_agent.py                   # ETA prediction (LLM-enriched)
│   ├── notification_agent.py          # Customer notifications (tone-aware)
│   ├── llm.py                         # OpenRouter client with retry
│   └── tools/
│       └── supply_chain_tools.py      # 7 tools agents can call
├── generators/
│   ├── seed_data.py                   # Warehouses, products, customers, trucks
│   ├── seed_pipeline.py               # Fast seed for instant dashboard data
│   ├── scenarios.py                   # 8 disruption scenarios
│   ├── order_gen.py                   # Order stream
│   ├── warehouse_gen.py               # Warehouse processing + random delays
│   ├── shipment_gen.py                # Shipment creation
│   └── gps_gen.py                     # GPS ping emitter
├── sql/
│   ├── 01-tables.sql                  # 5 source tables
│   └── 02-materialized-views.sql      # 6 streaming MVs (with MV chaining)
├── scripts/
│   ├── setup_schema.py                # Apply DDL to RisingWave
│   ├── run_generators.py              # Run all generators (CLI)
│   ├── run_agent.py                   # Run disruption agent (CLI)
│   ├── run_demo.py                    # Full orchestrated demo (CLI)
│   ├── trigger_disruption.py          # Inject chaos
│   ├── reset.py                       # Clear all data
│   └── dashboard_query.py             # CLI dashboard
├── config.py                          # Shared config (.env + st.secrets)
├── db.py                              # RisingWave connection helper
├── requirements.txt                   # Python dependencies
├── pyproject.toml                     # Project metadata
└── README.md
```

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
| `OPENROUTER_MODEL` | LLM model for AI agents | |
| `GENERATOR_SPEED` | Speed multiplier | `1.0` |

## Tech Stack

- **[RisingWave](https://risingwave.com)** — Streaming database with PostgreSQL-compatible SQL
- **[Streamlit](https://streamlit.io)** — Real-time web dashboard, deployable to Streamlit Cloud
- **[OpenRouter](https://openrouter.ai)** — LLM API for AI agent reasoning
- **[Plotly](https://plotly.com)** — Interactive charts
