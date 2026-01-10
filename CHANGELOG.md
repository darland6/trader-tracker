# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
