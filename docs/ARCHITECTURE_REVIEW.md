# Architecture Review & Optimization Plan

## Self-Reflection Analysis

After reviewing the codebase structure, here's an honest assessment of the current architecture and recommendations for simplification.

---

## Current State: Issues Identified

### 1. **Service Layer Duplication**

| Files | Issue |
|-------|-------|
| `alt_history.py` + `alternate_reality.py` | Two services doing similar alternate timeline work |
| `future_projection.py` + `reality_projections.py` | Overlapping projection logic |
| `options_scanner.py` + `agent_scanner.py` | Scanner logic split unnecessarily |

**Impact**: Confusion about which service to use, duplicated code, inconsistent behavior.

### 2. **Route Layer Bloat**

Currently **18 route files** when the domain really has these concerns:
- Portfolio State (holdings, cash, value)
- Events (trades, options, deposits)
- Alternate Realities (what-if scenarios)
- AI Features (chat, insights, scanner)
- Configuration (settings, backup)
- Research (Dexter integration)

**Current routes:**
```
alt_history.py    alt_reality.py    backup.py
cash.py           chat.py           config.py
events.py         history.py        ideas.py
notifications.py  options.py        prices.py
research.py       scanner.py        setup.py
state.py          trades.py         web.py
```

**Should be:**
```
portfolio.py      # state, holdings, prices
events.py         # all event types: trades, options, cash, dividends
realities.py      # alternate histories, projections
ai.py             # chat, insights, scanner
admin.py          # config, backup, setup
web.py            # template serving
```

### 3. **Frontend Confusion**

Two separate frontends exist:
- `/dashboard/` - Three.js solar system visualization (Vite/npm)
- `/web/templates/` - Jinja2 server-rendered pages

**Issues:**
- `main.js` is 7000+ lines and growing
- Unclear which frontend to use for what
- Duplicated state management logic
- `realities.html` + `realities.js` duplicates concepts from dashboard

### 4. **LLM Integration Sprawl**

LLM calls are scattered:
- `llm/client.py` - core client
- `api/services/insights.py` - event insights
- `api/services/agent_scanner.py` - scanner LLM
- `api/routes/chat.py` - chat interface
- `cli/events.py` - CLI insights

**Should be**: Single `llm/` module with clear interfaces.

### 5. **Data Model Ambiguity**

- Events stored in CSV (source of truth)
- Events also in SQLite (for queries)
- Alternate histories in JSON files
- Price cache in SQLite
- Memory/insights in JSON files

**Should be**: Clear data layer with single source of truth.

---

## Proposed Simplified Architecture

```
trader-tracker/
├── api/
│   ├── main.py              # FastAPI app, CORS, WebSocket
│   ├── database.py          # All data access (events, prices, histories)
│   ├── models.py            # Pydantic models
│   └── routes/
│       ├── portfolio.py     # GET /state, /holdings, /prices, POST /prices/update
│       ├── events.py        # GET/POST events, trades, options, cash
│       ├── realities.py     # Alternate histories, projections, comparisons
│       ├── ai.py            # Chat, insights, scanner, recommendations
│       ├── admin.py         # Config, backup, setup
│       └── web.py           # Template serving
│
├── core/                    # Business logic (NEW - extract from services)
│   ├── portfolio.py         # Portfolio state reconstruction
│   ├── events.py            # Event processing and validation
│   ├── realities.py         # Alternate history engine
│   └── scanner.py           # Options analysis (merge scanners)
│
├── llm/                     # AI integration (consolidate)
│   ├── client.py            # LLM API calls (local + Claude)
│   ├── prompts.py           # All prompts in one place
│   └── tools.py             # LLM tool definitions
│
├── data/                    # Data storage
│   ├── events.csv           # Source of truth for events
│   ├── portfolio.db         # SQLite for queries + cache
│   └── realities/           # JSON alternate histories
│
├── web/                     # Server-rendered UI
│   ├── templates/           # Jinja2 templates (keep for forms)
│   └── static/              # Static assets
│
├── dashboard/               # Three.js visualization (keep separate)
│   └── src/
│       ├── main.js          # Entry point only
│       ├── scene.js         # Three.js scene setup
│       ├── planets.js       # Planet/holding visualization
│       ├── realities.js     # Multiverse visualization
│       ├── ui.js            # HUD and panels
│       └── api.js           # API client
│
├── cli/                     # Command-line interface
│   └── portfolio.py         # Single CLI entry point
│
└── tests/
    └── test_*.py
```

---

## Migration Plan

### Phase 1: Consolidate Services (Low Risk)
1. Merge `alt_history.py` + `alternate_reality.py` → `core/realities.py`
2. Merge `options_scanner.py` + `agent_scanner.py` → `core/scanner.py`
3. Merge projection services → `core/realities.py`
4. Delete redundant service files

### Phase 2: Simplify Routes (Medium Risk)
1. Combine related routes into 6 files
2. Update frontend API calls
3. Keep old routes as redirects temporarily

### Phase 3: Split Dashboard JS (Low Risk)
1. Extract `main.js` into logical modules
2. Use ES6 imports
3. Keep Vite bundling

### Phase 4: Consolidate Data Layer (Higher Risk)
1. Make CSV truly the only source of truth
2. SQLite becomes read-only cache
3. Clear data migration path

---

## What We Should NOT Change

1. **Event sourcing model** - This is working well
2. **Three.js visualization** - Core differentiator
3. **LLM integration points** - Just consolidate, don't remove
4. **CLI interface** - Useful for power users

---

## Metrics for Success

| Metric | Current | Target |
|--------|---------|--------|
| Route files | 18 | 6 |
| Service files | 15 | 5 (in core/) |
| main.js lines | 7000+ | <1500 (entry) |
| Duplicate code | ~20% est | <5% |

---

## Decision Required

This refactoring should be done incrementally to avoid breaking changes. Recommended approach:

1. **Start with Phase 1** (service consolidation) - Lowest risk, highest clarity gain
2. **Phase 3** (JS split) can be done in parallel - No backend impact
3. **Phase 2** (routes) after Phase 1 is stable
4. **Phase 4** only if data issues arise

**Estimated effort**:
- Phase 1: 2-3 focused sessions
- Phase 2: 1-2 sessions
- Phase 3: 1 session
- Phase 4: 2-3 sessions (if needed)

---

*Generated by Claude Code architecture review - 2026-01-12*
