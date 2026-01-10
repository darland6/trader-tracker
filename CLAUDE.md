# Financial Portfolio Management System

> Event-sourced portfolio tracker with CLI, Web UI, Three.js 3D visualization, and LLM-powered insights.

---

## Session Start Instructions

**At the start of each new Claude Code session, read `CHANGELOG.md` to understand recent changes and current state of the project.**

Key files to review:
- `CHANGELOG.md` - Recent changes, new features, and bug fixes
- `data/event_log_enhanced.csv` - Current portfolio events (source of truth)
- `portfolio.db` - SQLite database (synced from CSV)

Quick status commands:
```bash
# Check server status
curl -s http://localhost:8000/api/state | python3 -m json.tool | head -20

# View recent events
curl -s http://localhost:8000/api/events?limit=5

# Run tests
python -m pytest tests/ -v
```

---

## Project Statistics

| Metric | Value |
|--------|-------|
| **Total Project Size** | ~342 MB |
| **Source Code (Python)** | ~3,000 lines |
| **JavaScript (Dashboard)** | ~820 lines |
| **API Routes** | 8 endpoints |
| **Web Templates** | 7 HTML files |
| **Virtual Environment** | 270 MB |
| **Dashboard node_modules** | 69 MB |

---

## Directory Structure

```
C:\Users\cory\projects\finances\
│
├── api/                          [~15 KB] FastAPI backend
│   ├── __init__.py               (0 bytes)
│   ├── main.py                   (3.8 KB, 130 lines) - App init, WebSocket, CORS
│   ├── database.py               (5.0 KB, 167 lines) - SQLite schema & operations
│   ├── models.py                 (3.5 KB, 118 lines) - Pydantic request/response models
│   └── routes/                   [~12 KB] Endpoint handlers
│       ├── __init__.py           (0 bytes)
│       ├── state.py              (4.0 KB, 134 lines) - GET /api/state
│       ├── trades.py             (1.5 KB, 51 lines)  - POST /api/trades
│       ├── options.py            (3.5 KB, 116 lines) - /api/options/*
│       ├── cash.py               (2.1 KB, 70 lines)  - /api/cash/*
│       ├── prices.py             (2.2 KB, 75 lines)  - /api/prices/*
│       ├── events.py             (1.9 KB, 63 lines)  - GET /api/events
│       ├── backup.py             (6.0 KB, 200 lines) - /api/backup/*
│       └── web.py                (5.7 KB, 191 lines) - HTML template serving
│
├── cli/                          [~35 KB] Command-line interface
│   ├── __init__.py               (0 bytes)
│   ├── commands.py               (11 KB, 375 lines)  - CLI command handlers
│   ├── display.py                (7.3 KB, 245 lines) - Rich terminal formatting
│   ├── events.py                 (10.7 KB, 359 lines)- Event creation & AI integration
│   └── prompts.py                (6.6 KB, 220 lines) - Interactive user prompts
│
├── llm/                          [~14 KB] LLM integration layer
│   ├── __init__.py               (0.1 KB)
│   ├── client.py                 (6.5 KB, 218 lines) - Claude/local API client
│   ├── config.py                 (3.1 KB, 104 lines) - Configuration management
│   └── prompts.py                (4.4 KB, 146 lines) - System prompts for insights
│
├── web/                          [~68 KB] Web UI templates
│   └── templates/
│       ├── base.html             (4.2 KB) - Layout with DaisyUI/Tailwind
│       ├── dashboard.html        (8.5 KB) - Analytics dashboard
│       ├── trade.html            (5.8 KB) - Trade entry form
│       ├── options.html          (13.1 KB)- Options management
│       ├── events.html           (10.2 KB)- Event history with AI modal
│       ├── cash.html             (4.8 KB) - Cash transactions
│       └── settings.html         (11.0 KB)- Backup/restore & LLM config
│
├── dashboard/                    [~69 MB] Three.js 3D visualization
│   ├── src/
│   │   └── main.js               (25 KB, 820 lines) - 3D scene, planets, interactions
│   ├── index.html                (4.5 KB) - Dashboard entry with HUD
│   ├── vite.config.js            (0.5 KB) - Vite bundler config
│   ├── package.json              (0.4 KB) - Node dependencies
│   ├── node_modules/             [69 MB]  - npm packages
│   └── dist/                     [~1 MB]  - Production build
│
├── tests/                        [~2.4 KB]
│   └── test_e2e_workflow.py      (2.4 KB, 82 lines) - End-to-end tests
│
├── backups/                      Backup storage directory
│
├── venv/                         [270 MB] Python virtual environment
│
├── .claude/                      Claude Code settings
│
└── [Root Files]
    ├── portfolio.py              (4.5 KB, 160 lines) - CLI entry point
    ├── run_server.py             (1.3 KB, 45 lines)  - API server entry
    ├── requirements.txt          (336 bytes)         - Python dependencies
    ├── .env                      (347 bytes)         - Environment variables
    ├── llm_config.json           (221 bytes)         - LLM runtime config
    │
    ├── event_log_enhanced.csv    (4.7 KB)  - CANONICAL EVENT LOG
    ├── portfolio.db              (36 KB)   - SQLite database
    ├── starting_state.json       (653 bytes)- Initial portfolio state
    ├── agent_context.json        (5.3 KB)  - LLM context snapshot
    ├── reason_taxonomy.json      (1.7 KB)  - Decision categorization
    │
    ├── PROJECT_SPECIFICATION.md  (13 KB)   - System requirements
    ├── README_Event_Sourcing.md  (11 KB)   - Architecture docs
    ├── README_AI_Agent_Integration.md (16 KB)
    ├── AI_Learning_System_Explained.md (21 KB)
    ├── portfolio_prediction_system.md (41 KB)
    └── ai_agent_prompt.md        (8.5 KB)  - LLM system prompt
```

---

## Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INTERACTION                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   CLI (portfolio.py)          Web UI (/manage)         3D Dashboard         │
│         │                          │                   (/dashboard)         │
│         │                          │                        │               │
│         ▼                          ▼                        │               │
│   ┌───────────┐            ┌─────────────┐                  │               │
│   │ cli/      │            │ web/        │                  │               │
│   │ commands  │            │ templates/  │                  │               │
│   │ prompts   │            │ (Jinja2)    │                  │               │
│   │ display   │            └──────┬──────┘                  │               │
│   └─────┬─────┘                   │                         │               │
│         │                         │                         │               │
│         ▼                         ▼                         ▼               │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                        FastAPI Backend                               │   │
│   │                         (api/main.py)                               │   │
│   │                                                                     │   │
│   │  Routes:                                                            │   │
│   │  ├── /api/state    → Portfolio holdings, cash, P&L                  │   │
│   │  ├── /api/trades   → Execute buy/sell                               │   │
│   │  ├── /api/options  → Open/close/expire/assign options               │   │
│   │  ├── /api/cash     → Deposits/withdrawals                           │   │
│   │  ├── /api/prices   → Stock price updates                            │   │
│   │  ├── /api/events   → Event history queries                          │   │
│   │  ├── /api/backup   → Export/import/restore                          │   │
│   │  └── /ws           → WebSocket real-time updates                    │   │
│   └──────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                          │
│                                  ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────┐   │
│   │                         cli/events.py                               │   │
│   │                    (Event Creation Engine)                          │   │
│   │                                                                     │   │
│   │  1. Validate event data                                             │   │
│   │  2. Generate AI insights (optional)                                 │   │
│   │  3. Append to CSV log                                               │   │
│   │  4. Sync to SQLite                                                  │   │
│   └──────────────────────────────┬──────────────────────────────────────┘   │
│                                  │                                          │
│              ┌───────────────────┼───────────────────┐                      │
│              ▼                   ▼                   ▼                      │
│   ┌──────────────────┐ ┌─────────────────┐ ┌────────────────┐               │
│   │  event_log_      │ │  portfolio.db   │ │  llm/          │               │
│   │  enhanced.csv    │ │  (SQLite)       │ │  client.py     │               │
│   │                  │ │                 │ │                │               │
│   │  CANONICAL       │ │  - events       │ │  Claude API    │               │
│   │  SOURCE OF       │ │  - price_cache  │ │  or Local LLM  │               │
│   │  TRUTH           │ │                 │ │                │               │
│   └──────────────────┘ └─────────────────┘ └────────────────┘               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

                              ▼ STATE RECONSTRUCTION ▼

┌─────────────────────────────────────────────────────────────────────────────┐
│                      build_portfolio_state()                                │
│                       (api/routes/state.py)                                 │
│                                                                             │
│   Replays all events chronologically to compute:                            │
│   ├── holdings: { ticker: shares }                                          │
│   ├── cash: current balance                                                 │
│   ├── cost_basis: { ticker: { shares, total_cost, avg_cost } }              │
│   ├── active_options: [ { ticker, strike, exp, premium, uuid } ]            │
│   ├── ytd_income: trading_gains + option_income + dividends                 │
│   └── latest_prices: { ticker: price }                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Event Types & Schema

### Event Log Format (CSV)
```csv
event_id,timestamp,event_type,data_json,reason_json,notes,tags_json,affects_cash,cash_delta
```

### Event Types
| Type | Description | data_json Fields |
|------|-------------|------------------|
| `TRADE` | Buy/sell stock | ticker, action, shares, price, total |
| `OPTION_OPEN` | Sell option | ticker, strategy, strike, expiration, contracts, premium, uuid |
| `OPTION_CLOSE` | Buy back option | original_event_id, uuid, close_cost, gain |
| `OPTION_EXPIRE` | Expired worthless | original_event_id, uuid, full_premium |
| `OPTION_ASSIGN` | Got assigned | original_event_id, uuid, action, shares |
| `DEPOSIT` | Add cash | amount, source |
| `WITHDRAWAL` | Remove cash | amount, purpose |
| `PRICE_UPDATE` | Market data | prices: { ticker: price } |
| `DIVIDEND` | Dividend received | ticker, amount, shares |
| `NOTE` | Journal entry | content |
| `GOAL_UPDATE` | Income goal change | annual_goal |
| `STRATEGY_UPDATE` | Strategy change | strategy_name, details |
| `INSIGHT_LOG` | Daily AI usage log | date, run_count, first_run, last_run, last_model, event_types |

### AI Insights (in reason_json)
```json
{
  "primary": "INCOME_GENERATION",
  "secondary": "WILLING_TO_BUY",
  "confidence": "HIGH",
  "explanation": "User's reason text",
  "ai_insights": {
    "reasoning": "Analysis of the decision...",
    "future_advice": "What to watch for...",
    "past_reflection": "Similar to event #23..."
  },
  "ai_generated_at": "2026-01-09T10:30:00",
  "ai_model": "claude-sonnet-4-20250514"
}
```

---

## Entry Points & Commands

### CLI (portfolio.py)
```bash
# View portfolio
python portfolio.py view [--holdings] [--options] [--income]

# Trade stocks
python portfolio.py trade buy TSLA 10 --price 445 --reason "bullish"
python portfolio.py trade sell TSLA 5 --price 480 --gain 175

# Options trading
python portfolio.py option open BMNR put --strike 31 --exp 2026-02-28 --premium 4000
python portfolio.py option close 45 --cost 500
python portfolio.py option expire 45
python portfolio.py option assign 45

# Cash management
python portfolio.py cash deposit 5000 --source "Transfer"
python portfolio.py cash withdraw 1000 --purpose "Bills"

# Utilities
python portfolio.py prices              # Update stock prices
python portfolio.py history [--ticker TSLA]
python portfolio.py config show         # LLM settings
python portfolio.py config provider local
python portfolio.py config test
```

### API Server (run_server.py)
```bash
# Start server
python run_server.py [--port 8000] [--dev]

# Or directly with uvicorn
uvicorn api.main:app --reload --port 8000
```

### Dashboard Build
```bash
cd dashboard
npm install
npm run dev      # Development (port 5173)
npm run build    # Production build to dist/
```

### Portfolio Setup (scripts/setup_portfolio.py)
```bash
# Interactive setup wizard
python scripts/setup_portfolio.py

# Import from Schwab transaction history CSV
python scripts/setup_portfolio.py /path/to/Schwab_Transactions.csv

# Import from ticker-named lot export CSVs
python scripts/setup_portfolio.py /path/to/TSLA.csv /path/to/META.csv
```

**Schwab CSV Formats Supported:**
- **Transaction History** - Complete history export with all transaction types
- **Lot Details** - Per-ticker lot breakdown (e.g., "TSLA Lot Details for...")

---

## Web UI Routes

| Path | Template | Description |
|------|----------|-------------|
| `/` | dashboard.html | Portfolio overview & analytics |
| `/trade` | trade.html | Buy/sell stock form |
| `/options` | options.html | Options management |
| `/cash` | cash.html | Deposit/withdraw |
| `/events` | events.html | Event history with AI insights |
| `/settings` | settings.html | Backup/restore, LLM config |
| `/dashboard` | (Three.js) | 3D solar system visualization |

---

## API Endpoints

### State & Data
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/state` | Full portfolio state |
| GET | `/api/events` | Event history |
| GET | `/api/events/{id}` | Single event |

### Trading
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/trades` | Execute trade |
| POST | `/api/options/open` | Open option position |
| POST | `/api/options/close/{id}` | Close option |
| POST | `/api/options/expire/{id}` | Mark expired |
| POST | `/api/options/assign/{id}` | Mark assigned |

### Cash & Prices
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/cash/deposit` | Deposit funds |
| POST | `/api/cash/withdraw` | Withdraw funds |
| POST | `/api/prices/update` | Refresh stock prices |
| GET | `/api/prices` | Get cached prices |

### Backup/Restore
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/backup/list` | List backups |
| POST | `/api/backup/create` | Create backup |
| GET | `/api/backup/download/{file}` | Download backup |
| POST | `/api/backup/restore/{file}` | Restore from backup |
| POST | `/api/backup/upload` | Upload & restore |
| DELETE | `/api/backup/{file}` | Delete backup |

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `ws://localhost:8000/ws` | Real-time updates |

---

## Dependencies

### Python (requirements.txt)
```
# Data Processing
pandas>=2.0.0
numpy>=1.24.0
matplotlib>=3.7.0
openpyxl>=3.1.0

# Web Framework
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.6
websockets>=12.0
pydantic>=2.5.0
jinja2>=3.1.0
aiofiles>=23.0.0

# Finance Data
yfinance>=0.2.0
requests>=2.28.0

# LLM Integration
anthropic>=0.18.0
httpx>=0.25.0
python-dotenv>=1.0.0

# CLI & Testing
rich>=13.0.0
pytest>=7.0.0
```

### JavaScript (dashboard/package.json)
```json
{
  "dependencies": {
    "three": "^0.160.0",
    "gsap": "^3.12.0",
    "chart.js": "^4.4.0"
  },
  "devDependencies": {
    "vite": "^5.0.0"
  }
}
```

---

## Configuration Files

### .env
```bash
# LLM Configuration
LLM_PROVIDER=local              # "claude" or "local"
ANTHROPIC_API_KEY=sk-ant-...    # For Claude API
LOCAL_LLM_URL=http://192.168.50.10:1234/v1
LOCAL_LLM_MODEL=mistral-7b
LLM_ENABLED=true
```

### llm_config.json
```json
{
  "provider": "local",
  "enabled": true,
  "local_url": "http://192.168.50.10:1234/v1",
  "local_model": "mistral-7b",
  "claude_model": "claude-sonnet-4-20250514",
  "timeout": 30,
  "max_history_events": 10
}
```

---

## Database Schema (SQLite)

### events table
```sql
CREATE TABLE events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    data_json TEXT,
    reason_json TEXT,
    notes TEXT,
    tags_json TEXT DEFAULT '[]',
    affects_cash INTEGER DEFAULT 0,
    cash_delta REAL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);

CREATE INDEX idx_event_type ON events(event_type);
CREATE INDEX idx_timestamp ON events(timestamp);
CREATE INDEX idx_is_deleted ON events(is_deleted);
```

### price_cache table
```sql
CREATE TABLE price_cache (
    ticker TEXT PRIMARY KEY,
    price REAL,
    last_updated TEXT
);
```

---

## Three.js Dashboard Features

### Visualization
- **Sun** = Total portfolio value (center)
- **Planets** = Individual holdings (size proportional to % of portfolio)
- **Planet Colors** = Ticker-specific (TSLA=silver, META=blue, etc.)
- **Atmosphere Glow** = Green (gain) or Red (loss)
- **Particle Rings** = Momentum indicator
- **Saturn-like Rings** = High momentum (>20% gain/loss)

### Interactions
- **Click Planet** = Zoom in, show info popup, camera follows orbit
- **Click Sun** = Zoom out to system view
- **Mouse Hover** = Pointer cursor on clickable objects
- **Orbit Controls** = Pan, zoom, rotate with mouse
- **Auto-rotate** = Slow system rotation when viewing all

### HUD Elements
- Total portfolio value
- Cash balance
- Holdings value
- YTD income progress (goal: $30,000)
- Holdings grid with click-to-focus

---

## Build & Run

### Quick Start
```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Build dashboard
cd dashboard && npm install && npm run build && cd ..

# 4. Start server
python run_server.py

# 5. Open browser
#    Web UI: http://localhost:8000/
#    3D Dashboard: http://localhost:8000/dashboard
#    API Docs: http://localhost:8000/docs
```

### Development Mode
```bash
# Terminal 1: API server with reload
uvicorn api.main:app --reload --port 8000

# Terminal 2: Dashboard dev server
cd dashboard && npm run dev
```

---

## Key Design Decisions

1. **Event Sourcing**: All state derived from immutable event log (CSV as truth, SQLite for queries)
2. **Dual LLM Support**: Toggle between Claude API and local LLM (OpenAI-compatible)
3. **AI Insights**: Automatic reasoning, advice, and reflection on every user action
4. **3D Visualization**: Portfolio as solar system metaphor (holdings orbit the total value)
5. **No Database Migrations**: State reconstructed by replaying events
6. **Backup Safety**: Auto-backup before any restore operation

---

*Generated by Claude Code - Last updated: 2026-01-09*
