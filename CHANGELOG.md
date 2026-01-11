# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added - Persistent LLM Memory System (2026-01-10)

AI assistant now remembers context across sessions:

#### Memory Service (`api/services/memory.py`)
- **Conversation Summaries** - After each chat, LLM generates a summary with intent, key facts, and patterns
- **Context Injection** - Previous memories automatically included in system prompts
- **1GB File Cap** - Auto-prunes oldest 25% of entries when limit approached
- **Key Fact Extraction** - Important information preserved for future reference
- **Pattern Learning** - Tracks user trading patterns and preferences

#### API Endpoints
```
GET /api/chat/memory/stats   - Memory file statistics (size, count, usage %)
GET /api/chat/memory/context - Preview injected memory context
```

#### Memory Entry Structure
```json
{
  "summary": "User asked for a list of owned stocks...",
  "intent": "informational",
  "key_facts": ["BMNR, TSLA owned", "total holdings $819K"],
  "learned_patterns": ["prefers detailed breakdowns"],
  "tags": ["portfolio", "holdings"]
}
```

### Improved - Timeline Playback Animation (2026-01-10)

Smooth, time-based timeline animation for alternate reality comparisons:

#### Time-Based Playback
- **requestAnimationFrame** - 60fps smooth animation instead of interval-based
- **Real Date Interpolation** - Animates through actual calendar dates, not just data points
- **Interpolated Date Display** - Shows "Jan 15, 2025" between monthly data points

#### Speed Control
- **Adjustable Playback Speed** - ◀/▶ buttons to control speed
- **Presets**: 1 week/sec, 2 weeks/sec, 1 month/sec (default), 2-3-6 months/sec, 1 year/sec
- **Human-Readable Display** - Shows "1 mo/sec" or "2 wk/sec"

### Changed - LLM Configuration Single Source of Truth (2026-01-10)

Consolidated model configuration to prevent confusion:

- **Single Source**: Model names now ONLY come from `llm_config.json`
- **Removed Env Override**: `LOCAL_LLM_MODEL` no longer read from `.env`
- **Clearer Separation**: `.env` for URLs/secrets, `llm_config.json` for model settings

### Added - Options Income Scanner (2026-01-10)

New floating action button and scanner system for finding premium-selling opportunities:

#### Options Scanner Service (`api/services/options_scanner.py`)
- **Parallel Scanning** - Uses ThreadPoolExecutor with 5 workers to scan multiple tickers concurrently
- **Options Chain Analysis** - Fetches real-time options data via yfinance
- **Dual Strategy Support**
  - **Covered Calls** - For holdings with 100+ shares
  - **Cash-Secured Puts** - Based on available cash (max 50% per position)
- **Scoring Algorithm** (0-100 points)
  - Annualized premium yield (0-40 pts)
  - OTM safety margin (0-25 pts)
  - Delta/probability of profit (0-20 pts)
  - DTE sweet spot 30-45 days (0-10 pts)
  - Liquidity volume/open interest (0-5 pts)
- **LLM Integration** - Optional AI analysis for recommendation reasoning

#### API Endpoints (`api/routes/scanner.py`)
```
GET  /api/scanner/recommendations         - Quick scan with defaults
GET  /api/scanner/recommendations/analyze - Scan with LLM analysis
POST /api/scanner/scan                    - Full scan with custom parameters
GET  /api/scanner/ticker/{ticker}         - Scan specific ticker
```

#### Frontend
- **Floating Action Button** - Green pulsing "$" button in command deck
- **Scanner Modal** - Shows portfolio summary, recommendations sorted by score
- **AI Analyze Button** - Runs scan with LLM-powered insights

### Changed - Command Deck UI Redesign (2026-01-10)

Complete UI overhaul with spaceship cockpit aesthetic:

#### Visual Design
- **Orbitron Font** - Futuristic sci-fi headers and values
- **Share Tech Mono** - Terminal/console body text
- **Cyan/Blue Color Scheme** - Glowing accents and borders
- **Corner Brackets** - Frame the viewport like a cockpit display
- **Animated Scan Line** - Sweeps across the screen every 4 seconds
- **Panel Status Indicators** - Green pulsing dots on each panel

#### Control Panel Layout
- **Left Console** - System Status (total value, cash, holdings, income progress)
- **Right Console** - Controls (Trade, Options, Web UI, Settings buttons)
- **Top Center** - Mode indicator (History Mode toggle)
- **Bottom Console** - Holdings Array grid with all positions
- **Insights Console** - AI Insights panel (collapsible with +/- toggle)
- **Legend Console** - Visual guide (minimized by default)
- **Chat Console** - AI Assistant (minimized by default)
- **Scanner FAB** - Income Scanner button with pulsing green glow

#### Styling
- All panels use `.control-panel` class with gradient backgrounds
- Glowing borders and hover effects on interactive elements
- Modals styled to match command deck theme
- Settings panel slides in from the right

### Added - Description-Influenced Projections (2026-01-10)

Alternate reality descriptions now directly influence future projection calculations:

#### LLM Analysis
- History context (name, description) passed to LLM prompts
- Scenario-aware analysis considers user's stated intent

#### Statistical Analysis
- **Keyword Parsing** - Detects bull/bear/tech keywords in descriptions
- **Growth Multipliers**
  - Bull keywords (moon, rocket, aggressive): 1.5x growth
  - Bear keywords (crash, recession, conservative): 0.5x growth, 1.5x volatility
  - Tech keywords (AI, software, cloud): 1.3x growth
- **Noise Bias** - Bearish scenarios get negative noise bias to ensure lower projections

#### Frame Generation
- Scenario-appropriate random walk with directional bias
- Tighter bounds for bearish scenarios to prevent unrealistic gains

### Fixed - Cluster View Improvements (2026-01-10)

- **Leaderboard Fix** - Alternates now show actual percentages (was showing 0%)
  - Separated value calculation from 3D updates
  - Added reality price fallback for alternates without price data
- **Timeline UI Cleanup** - Properly removes cluster UI when exiting view
- **Extreme Relative Visualization**
  - Power curve amplification: losers crushed (0.3x), winners boosted (1.7x)
  - Scale range: 0.15x to 4x based on relative performance
  - Y-position offset: winners float up, losers sink down
  - Enhanced glow scaling and label opacity changes

### Added - Income Events Modal (2026-01-10)

Quick access to view income-generating events from the dashboard:

- **Clickable Income Row** - Click YTD income value to open modal
- **Year Links** - "This Year" and "Last Year" quick filters
- **Summary Stats** - Breakdown by options, dividends, trading gains
- **Event List** - Shows date, type, description, and amount for each event

### Added - Alternate Reality & Future Projections (2026-01-10)

Explore "what-if" scenarios and project portfolio futures with AI-powered analysis.

#### Alternate Reality System
- **Ethereum Pyramid** in 3D dashboard - Click to open alternate reality modal
  - Octahedron geometry with pulsing glow effect
  - Orbits the sun at a mysterious outer distance
- **Alternate History Builder**
  - Create modified versions of your portfolio history
  - Modification types: remove ticker, scale position, add hypothetical trade
  - Compare any two realities side-by-side
- **Quick Scenarios**
  - "What if I never bought X?" - Removes all trades for a ticker
  - "What if I doubled down on X?" - Scales position by 2x
- **Persistent Storage** - Alternate histories saved to `data/alt_histories/`

#### Future Projections
- **3-5 Year Portfolio Projections** from current reality or any alternate
- **AI Analysis Mode** (when LLM available)
  - Per-ticker catalysts, industry trends, seasonality patterns
  - Macro outlook (interest rates, inflation, GDP)
  - Confidence levels for each projection
- **Statistical Analysis Mode** (fallback)
  - Sector-based growth profiles
  - Historical volatility patterns
- **Three Scenarios** - Pessimistic, Base, Optimistic projections
- **Timeline Visualization** - Monthly value bars with hover tooltips
- **Saved Projections** - Persist to `data/projections/` for later viewing

#### API Endpoints
```
GET    /api/alt-history                    - List alternate histories
POST   /api/alt-history                    - Create new alternate
GET    /api/alt-history/{id}               - Get history with state
DELETE /api/alt-history/{id}               - Delete history
POST   /api/alt-history/{id}/modify        - Apply modifications
GET    /api/alt-history/{id}/compare/{id2} - Compare two histories
GET    /api/alt-history/projections        - List saved projections
POST   /api/alt-history/projections/generate - Generate new projection
GET    /api/alt-history/projections/{id}   - Get saved projection
DELETE /api/alt-history/projections/{id}   - Delete projection
```

#### Cluster Visualization (2026-01-10)
- **Cluster View Button** in modal header opens immersive 3D comparison
- **Multiple Mini Solar Systems** arranged in circular cluster
  - Reality shown with gold sun, alternates with purple
  - Each system has orbiting planets matching holdings
- **Timeline Scrubber** to animate all systems through 3-year projection
  - Play/pause button for auto-playback
  - Date display shows current projection point
- **Leaderboard Overlay** ranks timelines by growth percentage
  - Gold/silver/bronze medals for top performers
  - Updates in real-time as timeline progresses
- **Visual Feedback** - Systems and planets scale based on portfolio value growth

#### Future Ideas (Not Yet Implemented)
- **Visual Links** - Lines connecting same tickers across realities to show divergence
- **Gaussian Splat Generator** - Given a simple idea (e.g., "more aggressive on tech"),
  generate multiple variations at different intensities and compare

### Fixed - Cost Basis Calculation (2026-01-10)

- **Event Sorting Bug** - Events with same timestamp were processed in random order
  - SELLs could be processed before BUYs on the same day
  - Caused cost basis to go negative and corrupt calculations
  - TSLA was showing -$6,603 loss when actual gain was +$10,433
- **Fix**: Sort events by `[timestamp, event_id]` for deterministic ordering

### Added - Portfolio Reconciliation Tools (2026-01-10)

Tools and fixes for reconciling imported portfolio data with actual brokerage positions:

#### State Reconstruction Fixes
- **`reconstruct_state.py`** - Fixed option close matching logic
  - Now tries `option_id` first (most reliable for imported data)
  - Falls back to `position_id`, then `uuid`
  - Properly handles ADJUSTMENT and INSIGHT_LOG event types
- **ADJUSTMENT event type** - New event type for cash reconciliation and position cleanup

#### Position Cleanup
- Fractional share cleanup (sells tiny positions at $0)
- Expired option cleanup (auto-expire old options from transaction history)
- Option position consolidation (combine multiple open events into single position)
- Cash reconciliation to match exact account balance

#### Debug Tools
- **`scripts/llm_debug.py`** - LLM connection diagnostics
  - Tests local LLM server connectivity
  - Validates model availability
  - Tests chat completion endpoint
  - Shows detailed error messages

#### Usage
```bash
# Run LLM diagnostics
python scripts/llm_debug.py

# Portfolio reconciliation is done via event adjustments
# See /reconcile skill for guided workflow
```

### Added - Schwab Transaction History Import (2026-01-10)

Complete brokerage history import from Schwab CSV exports:

#### New Adapter Function
- **`schwab_transaction_history_adapter()`** in `scripts/setup_portfolio.py`
  - Parses Schwab "Transactions" CSV export format
  - Handles all transaction types:
    - **Buy/Sell** - Stock trades with price, quantity, fees
    - **MoneyLink Transfer** - Deposits from linked bank accounts
    - **Qualified Dividend / Non-Qualified Div** - Dividend income
    - **Bank Interest** - Interest on cash balance
    - **Sell to Open / Buy to Close** - Short option trades
    - **Buy to Open / Sell to Close** - Long option trades
    - **Expired** - Option expirations
    - **Stock Plan Activity** - RSU vesting (recorded as $0 cost buys)
    - **Journal** - Tax withholding and internal transfers
    - **Wire Funds Received** - Wire transfer deposits
  - Parses option symbols (e.g., "BMNR 01/30/2026 31.00 P") to extract ticker, expiration, strike, type
  - Converts dates from MM/DD/YYYY to ISO format

#### New Import Function
- **`rebuild_from_schwab_history()`** - Rebuilds entire event log from Schwab export
  - Creates chronologically sorted events from all transactions
  - Shows summary by event type with cash impact
  - Calculates and displays final holdings
  - Reports final cash balance

#### Prior Position Reconciliation
- Automatically detects positions sold without corresponding buys (transferred in, vested before history)
- Adds adjustment events at start of history to reconcile holdings
- Cash balance adjustment to match actual account balance

#### Usage
```bash
python scripts/setup_portfolio.py /path/to/Schwab_Transactions.csv
```

### Added - Daily AI Insight Logging (2026-01-10)

New `INSIGHT_LOG` event type tracks AI insight generation:

- **One event per day** - Creates a single log event that gets updated throughout the day
- **Tracks run count** - Increments each time insights are generated
- **Event details include:**
  - `date` - ISO date string
  - `run_count` - Number of times insights generated today
  - `first_run` / `last_run` - Time of first and last generation
  - `last_model` - LLM model used
  - `event_types` - List of event types that triggered insights
- **Location:** `llm/client.py` - `_log_daily_insight_usage()` function

### Added - 3D View Navigation Link (2026-01-10)

- Added "3D View" link to the navbar in `web/templates/base.html`
- Links to `/dashboard` for the Three.js solar system visualization
- Styled with primary color and globe icon to stand out

### Fixed - Event Status Overwriting Bug (2026-01-10)

Fixed bug where manually editing an option's status field was being overwritten:

- **Root cause:** `api/routes/web.py` and `api/routes/events.py` were dynamically computing and overwriting the `status` field for OPTION_OPEN events based on whether a corresponding close event existed
- **Fix:** Now only sets status if it's not already present in the event data
- **Files modified:** `api/routes/web.py`, `api/routes/events.py`

### Added - Historical Price Playback (2026-01-10)

History mode now uses real historical market prices for accurate portfolio value transitions:

#### Backend
- **Historical Prices Service** (`api/services/historical_prices.py`)
  - `fetch_historical_prices()` - Fetches daily closing prices from yfinance
  - `get_price_at_date()` - Gets price with fallback to nearest date
  - `generate_playback_frames()` - Creates daily frames with real prices
  - `prepare_full_playback()` - Main function for complete playback data

- **Prepared Playback Endpoint** (`GET /api/history/prepared-playback`)
  - Returns daily frames with historical market prices
  - Includes holdings values at actual market prices for each day
  - May take 10-30 seconds to load (fetches from yfinance)

#### Frontend (dashboard/src/main.js)
- Playback now uses daily frames with real historical prices
- Smooth transitions between days showing actual portfolio value changes
- Market days without events show "MARKET DAY" indicator
- Date card in holdings grid shows current playback date

### Fixed - Event Editing Cache Issues (2026-01-10)

- Added cache-busting to page reload after event edits
- Added no-cache headers to events page to ensure fresh data
- Synced partials/events_table.html to include all event fields (tags, affects_cash)
- Added console debug logging to track edit flow (open modal, submit, response)
- Backend edit API verified working (updates CSV and SQLite correctly)

### Added - Agentic Notification System (2026-01-10)

Full proactive notification infrastructure for agent-driven portfolio management:

#### Backend
- **Notifications Database** - New `notifications` and `agent_schedules` tables in SQLite
- **Notification API** (`/api/notifications`)
  - `GET /api/notifications` - List active notifications with counts
  - `GET /api/notifications/count` - Get counts by severity (urgent/warning/info)
  - `POST /api/notifications/{id}/dismiss` - Dismiss a notification
  - `POST /api/notifications/{id}/snooze` - Snooze for N hours
  - `POST /api/notifications/check` - Run all alert checks manually
  - `GET /api/notifications/scheduler/status` - View background scheduler status

- **Alert Rule Engine** (`api/services/alerts.py`)
  - Option expiration warnings (7d, 3d, 1d, TODAY, EXPIRED with escalating severity)
  - Price movement alerts (configurable threshold, default 5%)
  - Portfolio concentration alerts (positions >25%)
  - Income goal milestone notifications (25%, 50%, 75%, 100%)

- **Background Scheduler** (`api/services/scheduler.py`)
  - Auto price updates during market hours (15min regular, 30min extended)
  - Periodic alert checks every 5 minutes
  - WebSocket broadcast to all connected clients on updates

#### Frontend
- **Notification Bell** in navbar (all pages via `base.html`)
  - Badge showing unread count
  - Dropdown panel with notification list
  - Severity indicators (urgent=red, warning=orange, info=blue)
  - Dismiss and snooze buttons per notification
  - Action buttons (Review Option, View Position, Trade)
  - WebSocket connection for real-time updates
  - Auto-refresh fallback every 60 seconds

### Added - Auto Cash Delta Calculation (2026-01-10)

- **Edit events with automatic recalculation** - When editing event data, `cash_delta` is automatically recalculated from the event type and data fields
- **New endpoint** `POST /api/events/recalculate-all` - Recalculate cash_delta for ALL events to fix historical inconsistencies
- **UI update** - Cash delta field in edit modal now shows as read-only with "Auto-calculated" badge
- Calculation logic handles: TRADE (buy/sell), OPTION_OPEN/CLOSE/EXPIRE/ASSIGN, DEPOSIT, WITHDRAWAL, DIVIDEND

### Added - Price Update with Gain/Loss Tracking (2026-01-10)

- Price updates now calculate and log portfolio gain/loss from price changes
- Event data includes: `portfolio_before`, `portfolio_after`, `portfolio_change`, `portfolio_change_pct`
- Per-ticker breakdown with `old_price`, `new_price`, `change_pct`, `change_value`
- Events table shows portfolio change for PRICE_UPDATE events

### Added - Price Event Compaction (2026-01-10)

- Same-day PRICE_UPDATE events are automatically compacted
- Keeps only first and last event of each day
- Reduces event log bloat from frequent price checks
- New function `compact_price_events()` in `api/database.py`

### Fixed - Database Sync on Import (2026-01-10)

- Fixed database not syncing from CSV on module import
- Previously, sync only occurred during FastAPI startup event
- Now `sync_csv_to_db()` runs automatically when `api.database` is imported
- This ensures database always reflects CSV content regardless of how the code is accessed

### Fixed - Cash Calculation Bug (2026-01-10)

- Fixed `reconstruct_state.py` not applying `cash_delta` for OPTION_CLOSE, OPTION_EXPIRE, and OPTION_ASSIGN events
- All 27 tests now pass

### Changed - Repository Cleanup (2026-01-10)

- Removed duplicate file `assets/filename.xlsx` (was identical to `Darland_income.xlsx`)
- Renamed `claude.md` to `CLAUDE.md` (standard convention)
- Moved `dashboard-analytics-subagent.skill` to `skills/` directory
- Updated README with tests section and complete project structure

### Added - Local LLM Support for Dexter (2026-01-10)

- Dexter research agent now automatically uses local LLM when configured
- When portfolio system is set to use local LLM, Dexter receives the same configuration via environment variables:
  - `OPENAI_API_BASE` / `OPENAI_BASE_URL` - Local LLM endpoint
  - `OPENAI_MODEL` - Local model name
- Added `get_dexter_env()` helper function to build environment variables
- Updated `get_dexter_status()` to report local LLM configuration

### Changed - Project Reorganization (2026-01-10)

Reorganized root-level files into a cleaner directory structure:

#### New Directory Structure

- **`docs/`** - Documentation files
  - `ai_agent_prompt.md`
  - `AI_Learning_System_Explained.md`
  - `portfolio_prediction_system.md`
  - `PROJECT_SPECIFICATION.md`
  - `README_AI_Agent_Integration.md`
  - `README_Event_Sourcing.md`
  - `SKILL_README.md`

- **`data/`** - Data files (event log, config, state)
  - `event_log_enhanced.csv` - Canonical event log
  - `starting_state.json` - Initial portfolio state
  - `agent_context.json` - LLM context snapshot
  - `agent_context_reason_analysis.json` - Reason analysis data
  - `reason_taxonomy.json` - Decision categorization

- **`scripts/`** - Utility scripts
  - `generate_dashboard.py`
  - `prepare_for_agent.py`
  - `update_prices_with_dashboard.py`
  - `update_prices_yfinance.py`

- **`assets/`** - Images, PDFs, and Excel files
  - Dashboard screenshots and visualizations
  - Excel spreadsheets

#### Files Kept at Root
- `README.md` - Main project documentation
- `CLAUDE.md` - Claude Code instructions
- `LICENSE` - Project license
- `.gitignore` - Git ignore rules
- `requirements.txt` - Python dependencies
- `portfolio.py` - CLI entry point
- `run_server.py` - API server entry point
- `reconstruct_state.py` - Core state reconstruction module (used by many imports)

#### Updated Import Paths
All source files have been updated to reference the new data file locations:
- `cli/events.py`
- `cli/commands.py`
- `api/database.py`
- `api/main.py`
- `api/demo_data.py`
- `api/routes/state.py`
- `api/routes/backup.py`
- `api/routes/history.py`
- `api/routes/prices.py`
- `api/routes/setup.py`
- `llm/client.py`
- `tests/test_e2e_workflow.py`
- `scripts/prepare_for_agent.py`
