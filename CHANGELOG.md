# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
