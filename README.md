# Portfolio Tracker

A personal financial portfolio management system with event sourcing, 3D visualization, AI-powered insights, and intelligent agent capabilities.

## Features

- **Event-Sourced Architecture**: All portfolio changes stored as immutable events in CSV (single source of truth)
- **3D Solar System Visualization**: Interactive Three.js dashboard showing your portfolio as planets
- **AI-Powered Chat**: LLM integration (Claude or local) with memory, patterns, and insights
- **Skill Discovery**: Access 16+ skills from Anthropic's library for specialized tasks
- **Pattern Learning**: Agent learns your trading style and preferences over time
- **Alternate History**: "What-if" scenarios with timeline playback
- **Options Tracking**: Track puts and calls with profit/loss calculations
- **Web Management UI**: Full-featured interface for all operations

## Quick Start

```bash
# Clone and setup
git clone https://github.com/darland6/trader-tracker.git
cd trader-tracker
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Build dashboard
cd dashboard && npm install && npm run build && cd ..

# Start server
python -m uvicorn api.main:app --reload --port 8000

# Open http://localhost:8000/dashboard
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACES                         │
├──────────────────┬─────────────────────┬───────────────────────┤
│   Web UI (/manage)│  3D Dashboard       │   CLI (portfolio.py)  │
│   - Trade entry   │  - Solar system     │   - Quick commands    │
│   - Event history │  - AI chat panel    │   - Price updates     │
│   - Settings      │  - Timeline playback│   - Status checks     │
└────────┬─────────┴──────────┬──────────┴───────────┬───────────┘
         │                    │                      │
         ▼                    ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                             │
│   /api/state     - Portfolio state reconstruction               │
│   /api/events    - Event history and search                     │
│   /api/chat      - AI chat with memory and skills               │
│   /api/skills    - Skill discovery and management               │
│   /api/alt-history - Alternate timeline scenarios               │
│   /api/scanner   - Options opportunity scanner                  │
└────────┬────────────────────┬───────────────────────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐  ┌────────────────────────────────────────────┐
│  Event Log CSV  │  │           Agent Services                   │
│  (Source of     │  │  ┌──────────────────────────────────────┐  │
│   Truth)        │  │  │  Memory (memory.py)                  │  │
│                 │  │  │  - Conversation summaries            │  │
│  portfolio.db   │  │  │  - Learned patterns with confidence  │  │
│  (SQLite Cache) │  │  │  - User preferences                  │  │
└─────────────────┘  │  │  - Export/import knowledge           │  │
                     │  └──────────────────────────────────────┘  │
                     │  ┌──────────────────────────────────────┐  │
                     │  │  Insights (insights.py)              │  │
                     │  │  - Event analysis                    │  │
                     │  │  - Batch insight generation          │  │
                     │  │  - Topic reflection                  │  │
                     │  └──────────────────────────────────────┘  │
                     │  ┌──────────────────────────────────────┐  │
                     │  │  Skills (skill_discovery.py)         │  │
                     │  │  - Anthropic skills integration      │  │
                     │  │  - Search and auto-install           │  │
                     │  │  - Local skill support               │  │
                     │  └──────────────────────────────────────┘  │
                     └────────────────────────────────────────────┘
```

## Agent Chat System

The chat system is the core of the AI capabilities. It supports multiple commands:

### Event Search
```
[SEARCH_LOG: ticker:TSLA type:TRADE]     # Find TSLA trades
[SEARCH_LOG: date:2026-01]               # Find January events
[SEARCH_LOG: income]                      # Free text search
```

### Financial Research
```
[RESEARCH_QUERY: What was TSLA's revenue growth?]
```
Requires Dexter MCP server for deep financial analysis.

### Skill Discovery
```
[SKILL_SEARCH: frontend design]          # Search for skills
[SKILL_INSTALL: frontend-design]         # Install from Anthropic
[SKILL_USE: frontend-design]             # Load skill instructions
```

Available skills include: frontend-design, webapp-testing, mcp-builder, pdf, docx, pptx, xlsx, canvas-design, theme-factory, and more.

### Insight Generation
```
[ANALYZE_EVENT: 45]                      # Analyze event by ID
[ANALYZE_EVENT: last TSLA trade]         # By description
[GENERATE_INSIGHTS: TSLA]                # Batch for ticker
[REFLECT: options strategy]              # Topic reflection
```

### Pattern Learning
```
[LEARN_PATTERN: strategy_preference] Only sells puts on stocks willing to own
[LEARN_PATTERN: risk_tolerance] Prefers >10% OTM strikes
[LEARN_PATTERN: ticker_affinity] Frequently trades tech stocks
```

Categories: trading_style, risk_tolerance, position_sizing, timing_preference, ticker_affinity, strategy_preference, goal_alignment

## API Endpoints

### Core Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/state` | Current portfolio state |
| GET | `/api/events` | Event history |
| POST | `/api/trades` | Log a trade |
| POST | `/api/options/open` | Open option position |
| POST | `/api/cash/deposit` | Deposit cash |

### Chat & AI Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/chat/` | Chat with AI assistant |
| GET | `/api/chat/memory/unified` | Complete memory state |
| GET | `/api/chat/memory/export` | Export agent knowledge |
| POST | `/api/chat/memory/import` | Import knowledge |
| GET | `/api/chat/patterns` | Learned patterns |
| GET | `/api/chat/usage` | Token usage stats |

### Skills Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/skills` | List all skills |
| GET | `/api/skills/search?q=` | Search skills |
| POST | `/api/skills/install/{id}` | Install skill |
| GET | `/api/skills/{id}` | Get skill details |

### Alternate History Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/alt-history` | List alternate histories |
| POST | `/api/alt-history` | Create what-if scenario |
| GET | `/api/alt-history/{id}/playback` | Timeline playback data |
| POST | `/api/alt-history/what-if/never-bought?ticker=TSLA` | Quick what-if |

## Data Flow

### Event Creation Flow
```
User Action (Web UI / CLI / API)
         │
         ▼
┌─────────────────────┐
│  Validate Event     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Generate AI        │ (optional)
│  Insights           │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Append to CSV      │ ← Source of Truth
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Sync to SQLite     │ ← Query Cache
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Broadcast via      │
│  WebSocket          │
└─────────────────────┘
```

### State Reconstruction Flow
```
Request for Portfolio State
         │
         ▼
┌─────────────────────┐
│  Load starting_     │
│  state.json         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Replay all events  │ ← Chronologically
│  from event log     │
└──────────┬──────────┘
           │
           ├─── TRADE: Update holdings & cost basis
           ├─── OPTION_*: Track active options
           ├─── DEPOSIT/WITHDRAWAL: Update cash
           ├─── DIVIDEND: Add to income
           │
           ▼
┌─────────────────────┐
│  Computed State     │
│  - holdings{}       │
│  - cash             │
│  - cost_basis{}     │
│  - active_options[] │
│  - ytd_income       │
└─────────────────────┘
```

### Chat Knowledge Flow
```
User Message
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Build Context                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Portfolio   │  │ Recent      │  │ Memory Context           │  │
│  │ State       │  │ Events      │  │ - Past conversations     │  │
│  │ (live)      │  │ (50)        │  │ - Learned patterns       │  │
│  └─────────────┘  └─────────────┘  │ - User preferences       │  │
│                                    └─────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LLM Call                                    │
│  System Prompt + Context + User Message → Response              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Process Commands                                │
│  [SEARCH_LOG: ...]      → Search events, add results            │
│  [RESEARCH_QUERY: ...]  → Call Dexter, add results              │
│  [SKILL_SEARCH: ...]    → Search skills, show options           │
│  [SKILL_INSTALL: ...]   → Install skill from Anthropic          │
│  [SKILL_USE: ...]       → Load skill instructions               │
│  [ANALYZE_EVENT: ...]   → Generate insight context              │
│  [LEARN_PATTERN: ...]   → Save to memory with confidence        │
│  [MEMORY_SUMMARY]       → Parse and save to memory              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
                   Return Response
```

## Configuration

### LLM Configuration (`llm_config.json`)
```json
{
  "provider": "local",
  "enabled": true,
  "local_url": "http://192.168.50.10:1234/v1",
  "local_model": "meta/llama-3.3-70b",
  "claude_model": "claude-sonnet-4-20250514",
  "timeout": 180,
  "max_history_events": 10
}
```

### Environment Variables (`.env`)
```env
ANTHROPIC_API_KEY=sk-ant-...
LOCAL_LLM_URL=http://192.168.50.10:1234/v1
```

## Project Structure

```
trader-tracker/
├── api/
│   ├── routes/
│   │   ├── chat.py           # AI chat with all commands
│   │   ├── alt_history.py    # Alternate timeline scenarios
│   │   ├── scanner.py        # Options opportunity scanner
│   │   └── ...               # Other route modules
│   ├── services/
│   │   ├── memory.py         # Unified agent memory
│   │   ├── insights.py       # Insight generation
│   │   ├── skill_discovery.py# Anthropic skills integration
│   │   ├── historical_prices.py # Timeline playback
│   │   └── ...
│   └── main.py
├── dashboard/
│   ├── src/main.js           # 3D visualization + chat UI
│   └── index.html            # Dashboard entry point
├── data/
│   ├── event_log_enhanced.csv # Source of truth
│   ├── llm_memory.json       # Agent memory
│   └── llm_usage.json        # Token tracking
├── docs/
│   ├── AGENTIC_CHAT_DESIGN.md # Agent architecture design
│   └── ...
├── llm/
│   ├── client.py             # LLM API client
│   ├── config.py             # Configuration loader
│   └── prompts.py            # System prompts
├── tests/
│   └── test_e2e_workflow.py  # 43 e2e tests
├── reconstruct_state.py      # State reconstruction
├── portfolio.py              # CLI entry point
├── CHANGELOG.md              # Change history
├── CLAUDE.md                 # Claude Code instructions
└── requirements.txt
```

## Testing

```bash
# Run all tests (43 tests)
./venv/bin/python -m pytest tests/ -v

# Tests cover:
# - Event log loading and parsing
# - State reconstruction accuracy
# - Agent context preparation
# - Options scanner functionality
# - Session tracking
```

## Memory System

The agent memory persists across sessions:

### Memory Components
- **Conversation Summaries**: What was discussed, intent, key facts
- **Learned Patterns**: Trading behaviors with confidence scores
- **User Preferences**: Explicit settings
- **Key Insights**: High-value observations

### Memory File (`data/llm_memory.json`)
```json
{
  "conversation_memories": [
    {"timestamp": "...", "summary": "...", "intent": "...", "key_facts": []}
  ],
  "learned_patterns": [
    {"pattern": "...", "category": "...", "confidence": 0.8, "evidence_count": 3}
  ],
  "user_preferences": {},
  "project_context": {"key_insights": []}
}
```

### Export/Import Knowledge
```bash
# Export for backup or transfer
curl http://localhost:8000/api/chat/memory/export > agent_knowledge.json

# Import to another instance
curl -X POST http://localhost:8000/api/chat/memory/import \
  -H "Content-Type: application/json" \
  -d @agent_knowledge.json
```

## License

MIT License - see [LICENSE](LICENSE) file.

## Acknowledgments

- Three.js for 3D visualization
- FastAPI for the backend
- Anthropic Claude for AI capabilities
- Anthropic Skills library for specialized agents
