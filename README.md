# Portfolio Dashboard

A personal financial portfolio management system with event sourcing, 3D visualization, and AI-powered insights.

## Features

- **Event-Sourced Architecture**: All portfolio changes are stored as immutable events in a CSV log (the single source of truth)
- **3D Solar System Visualization**: Interactive Three.js dashboard showing your portfolio as a planetary system
- **AI-Powered Insights**: LLM integration (Claude or local) for trade analysis and portfolio chat
- **History Playback**: Replay your portfolio evolution over time
- **Options Tracking**: Track cash-secured puts and covered calls with profit/loss calculations
- **Web Management UI**: Full-featured web interface for logging trades, options, and cash events

## Architecture

```
data/event_log_enhanced.csv  <-- Source of truth (event log)
        |
        v
   portfolio.db              <-- SQLite cache (synced from CSV on startup)
        |
        v
    FastAPI Backend          <-- REST API + WebSocket
        |
    +---+---+
    |       |
    v       v
 Web UI   Three.js Dashboard
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ (for dashboard development)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/portfolio-dashboard.git
cd portfolio-dashboard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# (Optional) Install dashboard dependencies for development
cd dashboard
npm install
cd ..
```

### Running the Application

```bash
# Start the API server
uvicorn api.main:app --reload --port 8000

# Access the application:
# - Web UI: http://localhost:8000/manage
# - 3D Dashboard: http://localhost:8000/dashboard (after building)
# - API Docs: http://localhost:8000/docs
```

### First-Time Setup

When you first run the application with no data:

1. **Demo Mode**: Try with 6 months of sample trading data
2. **Start Fresh**: Begin with an empty portfolio and starting cash
3. **Import CSV**: Upload an existing event log to restore a portfolio

## Configuration

### LLM Setup

The AI assistant supports two providers:

**Claude (Anthropic)**
```bash
# Set your API key in .env
ANTHROPIC_API_KEY=sk-ant-...
```

**Local LLM (OpenAI-compatible)**
```bash
# Configure in .env or via the UI
LOCAL_LLM_URL=http://192.168.50.10:1234/v1
LOCAL_LLM_MODEL=nvidia/nemotron-3-nano
```

### Environment Variables

Create a `.env` file:

```env
# LLM Configuration
LLM_PROVIDER=local  # or "claude"
ANTHROPIC_API_KEY=sk-ant-...
LOCAL_LLM_URL=http://192.168.50.10:1234/v1
LOCAL_LLM_MODEL=nvidia/nemotron-3-nano

# Optional
LLM_ENABLED=true
```

## Usage

### CLI Commands

```bash
# Log a trade
python portfolio.py trade buy TSLA 10 --price 250 --reason "Bullish on AI"

# Log an option
python portfolio.py option TSLA 240 2024-02-16 --premium 500 --strategy "Secured Put"

# Log cash movement
python portfolio.py deposit 5000 --reason "Monthly contribution"

# View portfolio state
python portfolio.py status

# Update prices
python portfolio.py prices
```

### Web UI

Navigate to `http://localhost:8000/manage` to:
- View current portfolio state
- Log trades, options, and cash events
- Browse event history
- Manage backups

### 3D Dashboard

Navigate to `http://localhost:8000/dashboard` for:
- Interactive solar system visualization of your portfolio
- Chat with AI assistant about your portfolio
- History playback mode
- Real-time price updates

## 3D Visualization Legend

| Element | Meaning |
|---------|---------|
| **Sun** | Total portfolio value |
| **Planet Distance** | Portfolio allocation (closer = larger position) |
| **Planet Size** | Market value of the position |
| **Green Glow** | Position in profit |
| **Red Glow** | Position at a loss |
| **Rings** | High momentum (+/- 20% gain/loss) |
| **Particles** | Momentum intensity |

## Data Format

The event log CSV is the source of truth with these columns:

```csv
event_id,timestamp,event_type,data_json,reason_json,notes,tags_json,affects_cash,cash_delta
```

Event types:
- `TRADE` - Buy/sell stock transactions
- `OPTION_OPEN` - Open option position (sell put/call)
- `OPTION_CLOSE` - Close option early
- `OPTION_EXPIRE` - Option expired worthless
- `OPTION_ASSIGN` - Option assignment
- `DEPOSIT` - Cash deposit
- `WITHDRAWAL` - Cash withdrawal
- `DIVIDEND` - Dividend received
- `PRICE_UPDATE` - Price snapshot
- `NOTE` - General notes

## Development

### Dashboard Development

```bash
cd dashboard
npm run dev  # Starts Vite dev server on :5173

# Build for production
npm run build  # Output to dashboard/dist/
```

### API Development

```bash
uvicorn api.main:app --reload --port 8000
```

### Project Structure

```
trader-tracker/
├── api/                    # FastAPI backend
│   ├── routes/            # API endpoints
│   ├── database.py        # SQLite operations
│   └── main.py            # App entry point
├── cli/                    # CLI tools
│   └── events.py          # Event creation
├── dashboard/              # Three.js frontend
│   ├── src/main.js        # 3D visualization
│   └── index.html         # Dashboard UI
├── data/                   # Data files
│   ├── event_log_enhanced.csv  # Source of truth
│   ├── starting_state.json     # Initial portfolio state
│   └── *.json             # Config and context files
├── docs/                   # Documentation
│   └── *.md               # Architecture and system docs
├── scripts/                # Utility scripts
│   ├── prepare_for_agent.py
│   └── update_prices_*.py
├── assets/                 # Images, PDFs, Excel files
├── integrations/           # External tool integrations
│   └── dexter.py          # Dexter financial research agent
├── llm/                    # LLM integration
│   ├── client.py          # LLM client
│   ├── config.py          # Configuration
│   └── prompts.py         # System prompts
├── skills/                 # Claude Code skills
├── tests/                  # Test suite
│   └── test_e2e_workflow.py
├── web/                    # Web management UI
│   └── templates/         # Jinja2 templates
├── examples/               # Example files
│   └── event_log_template.csv
├── portfolio.py           # CLI entry point
├── reconstruct_state.py   # State reconstruction module
└── requirements.txt       # Python dependencies
```

### Running Tests

```bash
# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Run all tests
python -m pytest tests/ -v

# Run with coverage (requires pytest-cov)
python -m pytest tests/ --cov=. --cov-report=html
```

## Backup & Restore

The event log CSV is portable:

```bash
# Backup
cp data/event_log_enhanced.csv ~/backups/portfolio_$(date +%Y%m%d).csv

# Restore (via UI or copy)
cp ~/backups/portfolio_20240115.csv data/event_log_enhanced.csv
# Restart the server to sync
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Acknowledgments

- Three.js for 3D visualization
- FastAPI for the backend
- Anthropic Claude for AI insights
