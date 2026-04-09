# Supply Chain Control Tower Demo

**End-to-end supply chain monitoring + AI-powered disruption response**, built on [RisingWave](https://risingwave.com) streaming database.

## The Story

```
Orders come in → Warehouse processes them → Shipments go out → Trucks deliver
                              ↓
                         RisingWave
                     (6 materialized views)
                              ↓
                      3 AI Agents detect disruption
                      → reroute orders
                      → predict ETAs
                      → notify customers
```

**The wow moment:** One warehouse disruption cascades into delayed shipments, updated ETAs, and triggered alerts — then AI agents autonomously resolve it in seconds.

## Live Demo

The entire demo runs from a single browser tab:

```bash
PYTHONPATH=. .venv/bin/streamlit run web/app.py
```

1. Toggle **Data Generators** ON — orders start flowing
2. Toggle **AI Agents** ON — 3 agents start watching
3. Wait ~20 seconds for orders to build up
4. Select a disruption scenario and click **TRIGGER DISRUPTION**
5. Watch the cascade and agent response in real-time

## Architecture

```
Data Generators          RisingWave Cloud              AI Agents
─────────────────      ──────────────────────      ─────────────────
orders_gen.py     →    orders table                 disruption_agent.py
warehouse_gen.py  →    warehouse_events table   ←── ── queries MVs
shipment_gen.py   →    shipments table              eta_agent.py
gps_gen.py        →    gps_pings table              notification_agent.py
                       ↓                                ↓
                       6 materialized views          agent_actions table
                       (auto-updating)                  ↓
                       ↓                            Streamlit dashboard
                       Streamlit dashboard
```

## AI Agents

| Agent | What it does | Poll interval |
|-------|-------------|---------------|
| **Disruption Response** | Detects warehouse delays, queries cascade impact, reroutes VIP/express orders, escalates critical situations | 5s |
| **ETA Prediction** | Enriches low-confidence ETAs using LLM reasoning about traffic patterns, time-of-day, and route conditions | 15s |
| **Customer Notification** | Crafts personalized delay messages based on customer priority (VIP/express/standard) and delay severity | 10s |

## Disruption Scenarios

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
4. In **Settings > Secrets**, paste your credentials (see `.streamlit/secrets.toml.example`)
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
│   ├── config.toml                    # Streamlit theme (RisingWave dark)
│   └── secrets.toml.example           # Streamlit Cloud secrets template
├── web/
│   └── app.py                         # Streamlit dashboard (main entry point)
├── agents/
│   ├── disruption_agent.py            # Disruption response (reroute/escalate)
│   ├── eta_agent.py                   # ETA prediction (LLM-enriched)
│   ├── notification_agent.py          # Customer notifications (tone-aware)
│   ├── llm.py                         # OpenRouter client with retry
│   └── tools/
│       └── supply_chain_tools.py      # 7 tools agents can call
├── generators/
│   ├── seed_data.py                   # Warehouses, products, customers, trucks
│   ├── scenarios.py                   # 8 disruption scenarios
│   ├── order_gen.py                   # Order stream
│   ├── warehouse_gen.py               # Warehouse processing pipeline
│   ├── shipment_gen.py                # Shipment creation
│   └── gps_gen.py                     # GPS ping emitter
├── sql/
│   ├── 01-tables.sql                  # 5 source tables
│   └── 02-materialized-views.sql      # 6 streaming MVs
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
| `OPENROUTER_MODEL` | LLM model | `minimax/minimax-m2.5:free` |
| `GENERATOR_SPEED` | Speed multiplier | `1.0` |

## Tech Stack

- **[RisingWave](https://risingwave.com)** — Streaming database with PostgreSQL-compatible SQL
- **[Streamlit](https://streamlit.io)** — Real-time web dashboard
- **[OpenRouter](https://openrouter.ai)** — LLM API (minimax M2.5 free tier)
- **[Plotly](https://plotly.com)** — Interactive charts
