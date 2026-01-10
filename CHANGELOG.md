# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
