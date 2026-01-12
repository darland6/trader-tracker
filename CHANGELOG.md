# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed - Data Layer Consolidation: BEDROCK (2026-01-12)

**Code Name: BEDROCK** - Consolidated data layer with CSV as single source of truth

#### Architecture Changes
- **Created `core/data.py`** - New centralized data access layer for all event operations
  - `append_event()` - Single function for all event writes to CSV
  - `update_event()` - Modify existing events with file locking
  - `delete_event()` - Remove events from CSV
  - `load_events()` - Read events with optional JSON parsing
  - `get_event_by_id()` - Retrieve single event
  - `sync_to_cache()` - Rebuild SQLite from CSV

#### File Locking for Concurrency Safety
- **fcntl-based file locking** - Prevents concurrent write corruption
  - Shared locks for reads (`LOCK_SH`)
  - Exclusive locks for writes (`LOCK_EX`)
  - Lock file: `data/event_log_enhanced.csv.lock`

#### Updated Modules
- **`api/database.py`** - Now explicitly documented as READ-ONLY cache
  - Added clear comments: CSV is source of truth, SQLite is cache
  - `update_event()` and `delete_event()` marked DEPRECATED, delegate to core/data.py
  - `sync_csv_to_db()` is the ONLY way to populate events table
- **`cli/events.py`** - Uses core/data.py for all CSV writes
  - `append_event()` delegates to core with file locking
  - `load_events()` replaces direct pd.read_csv() calls
  - All event creation functions now use centralized layer

#### Data Flow (Before vs After)
**Before BEDROCK:**
```
Routes → cli/events.py → CSV (no locking) → api/database.py syncs
Routes → api/database.py → CSV + SQLite (mixed writes)
```

**After BEDROCK:**
```
Routes → cli/events.py → core/data.py → CSV (with locking) → sync_to_cache()
Routes → api/database.py → core/data.py → CSV (with locking) → sync_to_cache()
```

#### Benefits
- **Single Source of Truth** - CSV is authoritative, SQLite is rebuildable
- **Concurrency Safety** - File locking prevents race conditions
- **Data Integrity** - No accidental SQLite-only writes
- **Backward Compatible** - Existing code continues to work (delegates internally)
- **Easier Debugging** - Clear data flow path

#### Testing
- All 43 E2E tests pass after migration
- No breaking changes to API or CLI
- Documentation: `docs/DATA_LAYER_ARCHITECTURE.md`

### Changed - Dashboard Code Refactoring: PRISM (2026-01-12)

#### Modularization of dashboard/src/main.js
- **Split monolithic 7941-line file into ES6 modules** - Dramatic improvement in code maintainability
  - `scene.js` (124 lines) - Three.js scene, camera, renderer, controls, starfield
  - `api.js` (590 lines) - All 40+ backend API calls consolidated
  - `planets.js` (515 lines) - Planet creation, textures, atmosphere, animations
  - `main.js` (453 lines) - Entry point and orchestration
  - **Total: 1,682 lines** (down from 7,941 = **77% reduction** for core features)
- **Preserved all core functionality** - No breaking changes
  - 3D visualization, planet creation, camera controls
  - Click/hover interactions, HUD display
  - Portfolio data fetching, price updates
  - AI/MCP status checking
- **Build system verified** - Vite build successful (494 KB bundle unchanged)
- **Documentation added** - `REFACTORING_SUMMARY.md` and `MODULE_REFERENCE.md`
- **Original backed up** - `main_original.js` contains complete 7941-line original
- **Future modularization identified** - Tracker, Realities, UI, Effects modules (~5000 lines remaining)

### Added - Cosmic Timeline Visualization & AI Self-Reflection (2026-01-12)

#### Alternate Realities Cosmic Animations (`web/static/realities.js`)
- **Planet Birth Animation** - Stock purchases trigger particle cloud coalescing into new planet
  - Particles spawn at random positions and converge into planet position
  - 2-second animation with easing and fade-in
  - Planet appears after particles coalesce
- **Asteroid Collision Animation** - Stock sales trigger impact and debris
  - Impact flash effect at collision point
  - Debris particles scatter outward with rotation
  - Planet shrinks proportionally to shares sold
  - 1.5-second dramatic animation
- **Timeline Playback Controls** - Play button for smooth animation through history
  - Variable speed: 0.5x, 1x, 2x, 4x playback speeds
  - Date display during playback
  - Auto-stops at end of timeline
- **Ambient Background Animations** - Cosmic events based on portfolio performance
  - Green portfolio: comets, supernovas, nebula formation
  - Red portfolio: asteroid storms, collisions, star deaths
  - Distant solar systems as backdrop with orbiting mini-planets
- **LLM-Powered Projections** - Realities page now heavily uses LLM for:
  - Future timeline projections (3-year forecasts)
  - Macro event identification (earnings, Fed meetings, market events)
  - Per-reality narrative generation

#### Main Dashboard Ticker Tracking (`dashboard/src/main.js`)
- **Track Any Ticker** - New "📡 Track" button in command panel
  - Track stocks or crypto by entering ticker symbol
  - Planet spawns next to main solar system
  - Shows real-time price and day change (%, $)
- **Tracked Ticker Planets**
  - Distinct purple/magenta color scheme
  - Pulsing glow effect
  - Click to show popup with price details
- **Destroy Animation** - Remove tracked tickers with dramatic effect
  - Planet explodes with particle debris
  - Fragments scatter and fade
  - Confirms removal with notification
- **LocalStorage Persistence** - Tracked tickers saved across sessions
- **Removed Ethereum Pyramid** - Alternate reality pyramid removed from main view (realities page is now primary)

#### AI Self-Reflective Prompts (`llm/prompts.py`)
- **Socratic Self-Questioning** - LLM now asks itself 3-5 probing questions before generating insights
  - "Why did they make this decision NOW rather than waiting?"
  - "Is this consistent with their income goal or a deviation?"
  - "What are they potentially missing or not seeing?"
- **Enhanced Insight Structure** - JSON response includes `self_questions` array
- **Deep Reflection Prompt** - New comprehensive portfolio analysis prompt
  - Questions on performance, risk, behavior, opportunity cost, blind spots
  - Returns uncomfortable truths, hidden patterns, action items
- **Income Scanner Prompt** - Options analysis with self-dialogue
  - Market condition assessment before recommendations
  - Rejected opportunities with reasoning

#### Agent Scanner Self-Questioning (`api/services/agent_scanner.py`)
- **7 Self-Questions** before making recommendations:
  1. "What's the current market sentiment and how does it affect option premiums?"
  2. "Which of these stocks would I actually want to own at the put strike prices?"
  3. "Am I recommending high-premium options because they're good or because they look attractive?"
  4. "What's the realistic probability of assignment and am I okay with that outcome?"
  5. "Is this portfolio overexposed to any sector or correlation risk?"
  6. "How close is this portfolio to its income goal and what's the appropriate risk level?"
  7. "What information am I missing that would change my recommendations?"
- **Self-Reflection in Response** - JSON includes `self_reflection` object with:
  - `key_question_answered` - Most important self-question and answer
  - `rejected_opportunities` - What was considered but rejected (and why)
  - `risk_concerns` - Concerns about any recommendations
- **Contrarian View** - Response includes "what could go wrong" perspective

#### Income Breakdown Year Selector
- **Year dropdown selector** - Choose which year to view income breakdown
  - Available years: current year and 4 previous years
  - API supports `?year=YYYY` query parameter
  - Auto-reloads data when year changes

#### Architecture Review Document (`docs/ARCHITECTURE_REVIEW.md`)
- **Self-Reflection Analysis** of current codebase structure
- **Issues Identified**:
  - Service layer duplication (alt_history.py + alternate_reality.py)
  - Route layer bloat (18 routes → should be 6)
  - Frontend confusion (dashboard vs web templates)
  - LLM integration sprawl across multiple files
  - Data model ambiguity (CSV vs SQLite vs JSON)
- **Proposed Simplified Architecture**:
  - Consolidated routes: portfolio, events, realities, ai, admin, web
  - New `core/` directory for business logic
  - Single source of truth for data
- **4-Phase Migration Plan** with priorities

### Added - Intraday Change Visuals & Expandable Dashboard Rows (2026-01-12)

#### Intraday Change Indicators on 3D Planets
- **Day change data** - API now returns `day_change_pct` and `day_change_value` for each holding
- **Pulsing arrow indicators** - Planets display vertical arrows (up/down) based on daily performance
- **Visual intensity** - Arrow size and glow intensity scales with % change (max at 5%)
- **Animated effects** - Pulsing beam, rotating ring, and bobbing arrow animation
- **HUD cards** - Holdings grid shows daily change with ▲/▼ indicator
- **Planet popup** - Clicking planet shows day change section with both % and $ values

#### Dashboard Expandable Rows
- **Income Breakdown expansion** - Tap Trading Gains/Options/Dividends to see individual transactions
- **Gains Summary expansion** - Tap Realized/Unrealized gains to see transaction details
- **Alpine.js integration** - Smooth collapse/expand animations with lazy loading
- **Tax calculations** - Shows estimated tax impact for each category

#### Ideas Lab Page (`/ideas`)
- **Dedicated page** - Full page for managing investment ideas
- **CRUD operations** - Create, view, edit, archive ideas
- **Status filtering** - Filter by seed, manifested, actionable, executed, archived
- **AI manifestation** - Generate actionable trades from seed ideas

### Added - Options BUY/SELL Tracking & Income Breakdown (2026-01-12)

#### Options BUY/SELL Action Field
- **New `action` field** - Options now track whether they were BUY or SELL
- **Pydantic validation** - Action must be "BUY" or "SELL" (case-insensitive)
- **Cash flow handling** - SELL = receive premium (positive), BUY = pay premium (negative)
- **Display improvements**:
  - Badge shows BUY (warning color) or SELL (success color)
  - Contracts shown as negative for SELL positions (matches Schwab display)
  - Premium label changes based on action (Received vs Paid)
- **Updated all existing options** - Migrated to include action: "SELL"

#### Premium Per Share Input
- **New input field** - Enter premium per share instead of total
- **Auto-calculation** - Total premium = per share × 100 × contracts
- **Live preview** - Shows calculated total before submission

#### Options Form Improvements
- **Rebuilt from scratch** - JavaScript form submission with proper validation
- **Duplicate prevention** - `isSubmitting` flag prevents double-submissions
- **Loading state** - Button shows spinner and "Saving..." during submission
- **Success feedback** - Shows success message before page redirect
- **Error handling** - Displays API errors in alert component

#### Income Breakdown API (`GET /api/income-breakdown`)
- **Individual transactions** - Lists each trade, option, and dividend separately
- **Tax calculations**:
  - Trades/options: 25% short-term capital gains rate
  - Dividends: 15% qualified dividend rate
- **Breakdown by category**:
  - `trades.transactions[]` - Each SELL trade with gain/loss
  - `options.transactions[]` - Each option premium received
  - `dividends.transactions[]` - Each dividend payment
- **Totals**: gross income, total tax, net after tax

#### Playwright E2E Tests (`tests/test_options_e2e.py`)
- **15+ comprehensive tests** for options functionality:
  - Page load verification
  - Form field visibility
  - Action selector (BUY/SELL options)
  - Premium label changes with action
  - Strategy selector (Put/Call)
  - API validation tests
  - Form submission tests (SELL and BUY)
  - Active options table verification
  - Negative contracts display for SELL
- **Auto-cleanup** - Test events removed from CSV after tests complete

#### Bug Fixes
- **Income breakdown empty data** - Fixed endpoint to use parsed `data` column from `load_event_log()` instead of raw `data_json`
- **Options form not working** - Fixed submit button selector to be more specific (`#option-form button[type='submit']`)

### Added - Ideas Lab & Projection Integration (2026-01-11)

#### Ideas Lab - Seed Investment Ideas System
- **New Event Types** - `IDEA_SEED`, `IDEA_ACTION`, `IDEA_STATUS` for tracking idea lifecycle
- **Full Ideas API** (`/api/ideas/`):
  - Create seed ideas with title, description, tickers, category, priority
  - Manifest ideas into concrete actions via LLM
  - Approve/reject/execute generated actions
  - Archive completed or abandoned ideas
- **LLM Manifestation** - AI analyzes your idea and generates 2-5 specific trade recommendations
  - Considers current portfolio context (cash, holdings, active options)
  - Generates sell put, sell call, buy stock, or research actions
  - Includes reasoning and risk assessment
- **Ideas Lab Panel** in dashboard:
  - Purple-themed UI matching the cosmic aesthetic
  - Create new ideas with category selection
  - View all ideas with status filtering
  - Manifest ideas with one click
  - Archive old ideas

#### Ideas as Toggleable Mods in Projections
- **Toggle Ideas in Future Tab** - When generating projections, toggle seed ideas on/off
- **Ideas affect projections**:
  - Income ideas boost projected premium income
  - Growth ideas boost growth rates for related tickers
  - Opportunity ideas add positions to projections
- **Visual feedback** - Loading indicator shows which ideas are being applied
- **`/api/ideas/as-mods`** - Get all ideas formatted for projection integration
- **`idea_ids` parameter** on `/api/alt-history/projections/generate`

#### Options Scanner Improvements
- **Granular Scoring (0-100)** - Continuous scoring instead of step increments
  - Premium yield: 0-40 points (linear scale 5-60% annualized)
  - Delta/risk: 0-30 points (prefers 0.15-0.35 delta)
  - DTE: 0-20 points (prefers 21-60 days)
  - Volume: 0-10 points (min 100 contracts)
  - Bonus: +10 for covered positions
- **Contract Recommendations** - Suggested, conservative, aggressive quantities
  - Based on income goal and position sizing rules
- **New Metrics Displayed**:
  - Assignment risk % (based on delta)
  - Break-even price (strike ± premium)
  - Time decay (theta per contract)

#### Settings Page Improvements
- **API Key Input** - Enter/update Anthropic API key from settings UI
- **Learning Files Section** - View all files used for learning/memory:
  - llm_memory.json, llm_usage.json, agent_context.json, etc.
  - Shows file descriptions and categories

#### Bug Fixes
- **Mixed Date Formats** - Fixed timestamp parsing to handle both ISO8601 and standard formats
- **Route Ordering** - Fixed `/as-mods` being captured by `/{idea_id}` route

### Added - Dashboard UI Testing & Chat Improvements (2026-01-11)

#### Playwright E2E Test Suite (`tests/test_dashboard_ui.py`)
- **33 Comprehensive Tests** for dashboard UI functionality:
  - Panel basics (loads, content verification)
  - Panel toggle (collapse/expand for chat, legend, insights)
  - Chat fullscreen mode (enter/exit, Escape key)
  - Panel dragging functionality
  - Panel resizing with resize handles
  - UI overlap detection (settings, panels, scanner button)
  - Alternate timeline mode (history mode, controls, close)
  - Settings panel (open, LLM options, close)
  - Timeline controls (scrubber, play button)
  - Responsive layout (mobile, tablet, desktop)
  - JavaScript error detection
- **Screenshot Capture** - Saves screenshots to `/tmp/dashboard_ui_tests/` for visual verification
- **Test Isolation** - Proper state management between tests

#### Bug Fixes Found & Fixed via E2E Testing
- **Settings Panel Z-Index** - Settings close button was blocked by right-console (Options button intercepted clicks)
  - Fixed by adding `z-index: 500` to `#settings-console` CSS
- **Chat Fullscreen State Management** - Fullscreen and minimized classes were conflicting
  - Fixed by properly managing class removal/addition in `toggleChatFullscreen()`
  - Exit fullscreen now restores minimized state with hidden body
- **Playback Toggle Button** - `querySelector('span')` was targeting wrong element (icon instead of text)
  - Fixed by using `querySelectorAll('span')[1]` to target text span
  - Added null checks for robustness

#### Chat Console Improvements
- **True Fullscreen Mode** - Chat now expands to full viewport (10px margins) with:
  - `z-index: 9000` to overlay all other elements
  - Flexbox layout for proper message/input distribution
  - Messages auto-scroll and pin at bottom
  - Escape key exits fullscreen
- **Repeat Message Button** - Hover over any user message to see "↻ Repeat" button
  - Clicking sends that message again (useful for retrying queries)
  - Styled to match UI theme
- **Improved Fullscreen CSS**:
  - User messages align right, assistant messages align left
  - Larger padding and font sizes in fullscreen mode
  - Border accent around fullscreen panel
- **Fixed Fullscreen Scroll** - Chat messages now properly scrollable in fullscreen mode
  - CSS flex layout fix: `flex: 1 1 0` with `height: 0` for proper overflow
  - Added Playwright test suite (`tests/test_chat_scroll.py`) to verify scroll functionality
- **Fixed LLM Response Cutoff** - Increased max_tokens from 1024 to 4096
  - Applies to all LLM calls: initial response, search follow-up, research follow-up
  - Prevents long AI responses from being truncated

#### Settings Page Enhancements
- **Learning & Memory Files Display** - New section in settings page showing all AI learning files:
  - `llm_memory.json` - Chat memory & conversation summaries
  - `llm_usage.json` - Token usage tracking
  - `agent_context.json` - Agent context & knowledge
  - `skill_cache.json` - Installed skills cache
  - `reason_taxonomy.json` - Decision reason categories
  - `agent_context_reason_analysis.json` - Reason analysis data
- **File Stats Display**:
  - Size in KB
  - Number of entries
  - Last modified date
  - Grouped by category (Memory, Analytics, Config, Skills)
- **New API Endpoint**: `GET /api/config/learning-files` returns file statistics

#### Development Workflow & Tooling
- **Playwright Browser Testing** - Used for visual verification and automated bug detection
- **Screenshot-Based Verification** - Key states captured for documentation
- **JavaScript Evaluation** - Some tests use `page.evaluate()` for more reliable toggle testing
- **Test Independence** - Each test loads fresh page to avoid state bleeding

### Added - MCP Integration & Income Tracking (2026-01-11)

#### Dexter MCP Integration (`integrations/dexter.py`)
- **Auto-detect MCP Host** - Infers MCP host from LLM config when using local LLM
- **SSE Transport Support** - Proper MCP JSON-RPC over Server-Sent Events
- **Session Management** - Maintains SSE connection for MCP session
- **Configurable via .env**:
  - `DEXTER_MCP_HOST` - Override MCP server host (auto-detected from LLM URL)
  - `DEXTER_MCP_PORT` - MCP server port (default: 3000)
- **Mandatory Dexter** - Chat system automatically uses Dexter for all financial queries
- **Fixed MCP SSE Bidirectional Protocol** (2026-01-11):
  - MCP SSE requires bidirectional communication: SSE for responses, POST for requests
  - POST returns `202 Accepted`, actual responses come via SSE stream
  - Rewrote `query_dexter_mcp()` to use raw sockets for proper bidirectional handling
  - Added proper MCP session initialization before tool calls
  - Added intelligent ticker extraction from natural language questions
  - Added tool selection based on question context (price, metrics, news, etc.)
  - Available tools: `get_price_snapshot`, `get_financial_metrics_snapshot`, `get_income_statements`, `get_balance_sheets`, `get_cash_flow_statements`, `get_news`, `get_insider_trades`, crypto endpoints

#### Realized/Unrealized Gains Tracking
- **Realized Gains/Losses** - Calculated from cost basis when gain_loss is 0 in imported data
- **YTD Filtering** - Only counts current year transactions for YTD totals
- **Separated Tracking**:
  - `ytd_realized_gains` - Positive gains from closed positions
  - `ytd_realized_losses` - Losses from closed positions (stored positive)
  - `ytd_trading_gains` - Net trading gains (gains - losses)
- **Unrealized Tracking** - Calculated from open holdings vs cost basis

#### Income API Enhancement (`api/routes/state.py`)
- **Full Income Breakdown**:
  - `realized_gains` - Gains from closed trading positions
  - `realized_losses` - Losses from closed positions
  - `trading_gains_net` - Net realized trading P&L
  - `unrealized_gains` - Open position paper gains
  - `unrealized_losses` - Open position paper losses
  - `unrealized_net` - Net unrealized P&L
  - `option_income` - Premium income from options
  - `dividends` - Dividend income

#### Chat Fullscreen Mode
- Added fullscreen expansion button `[ ]` to chat panel
- Press Escape to exit fullscreen
- Auto-focus input when entering fullscreen

#### MCP Network Expert Skill
- Created `/Users/cory/.claude/skills/mcp-network-expert/skill.md`
- Expert guidance for MCP server development
- Network troubleshooting and firewall configuration
- Cross-platform (Windows, macOS, Linux) support

### Added - Agentic Chat Package (2026-01-11)

Comprehensive agent capabilities with skills discovery, insight generation, pattern learning, and unified memory:

#### Skill Discovery System (`api/services/skill_discovery.py`)
- **Anthropic Skills Integration** - Access 16+ skills from https://github.com/anthropics/skills
- **Search & Suggest** - Find relevant skills based on task description
- **Auto-Install** - Install skills on-demand from Anthropic's repo
- **Local Skills** - Support for custom local skills
- **Chat Commands**:
  - `[SKILL_SEARCH: query]` - Search for relevant skills
  - `[SKILL_INSTALL: skill_id]` - Install a skill
  - `[SKILL_USE: skill_id]` - Load skill instructions

#### Insight Generation (`api/services/insights.py`)
- **Event Analysis** - Deep analysis of portfolio events with reasoning, advice, and reflection
- **Batch Insights** - Generate insights for multiple events by ticker or date
- **Topic Reflection** - Reflect on patterns around topics (options, risk, income, trading)
- **Insight Caching** - Cache generated insights to avoid regeneration
- **Chat Commands**:
  - `[ANALYZE_EVENT: id or description]` - Analyze specific event
  - `[GENERATE_INSIGHTS: ticker or date]` - Batch generate insights
  - `[REFLECT: topic]` - Generate reflection on topic

#### Pattern Learning (Enhanced `api/services/memory.py`)
- **Confidence Tracking** - Patterns have confidence scores that increase with evidence
- **Category System** - trading_style, risk_tolerance, position_sizing, timing_preference, ticker_affinity, strategy_preference, goal_alignment
- **Source Tracking** - Distinguishes stated vs observed vs inferred patterns
- **Pattern Merging** - Similar patterns consolidated with increased confidence
- **Chat Command**: `[LEARN_PATTERN: category] pattern description`

#### Unified Agent Memory
- **Unified State API** - Single endpoint for all memory components
- **Export/Import** - Backup and transfer agent knowledge between projects
- **Key Insights** - Store high-value observations that persist
- **Context Summary** - Concise summary for LLM prompt injection
- **API Endpoints**:
  - `GET /api/chat/memory/unified` - Complete memory state
  - `GET /api/chat/memory/export` - Export knowledge for backup
  - `POST /api/chat/memory/import` - Import knowledge from export
  - `POST /api/chat/memory/insight` - Add key insight
  - `GET /api/chat/patterns` - Get learned patterns

#### Skill Management API (`/api/skills`)
```
GET  /api/skills              - List all available skills
GET  /api/skills/search?q=    - Search skills by keyword
GET  /api/skills/suggest?task=- Suggest skill for task
POST /api/skills/install/{id} - Install skill from Anthropic
DELETE /api/skills/{id}       - Uninstall a skill
GET  /api/skills/{id}         - Get skill details/content
```

### Added - Timeline Playback with Daily Frames (2026-01-11)

Enhanced timeline playback with smooth daily interpolation:

#### Historical Prices Service (`api/services/historical_prices.py`)
- **Multi-Layer Data Sourcing**:
  1. yfinance for real market data
  2. Agent/Dexter fallback for missing data
  3. Linear interpolation to fill remaining gaps
- **Daily Frame Generation** - Creates frames for every day between events
- **Data Quality Tracking** - Reports which data source was used for each price

#### Playback API
```
GET /api/alt-history/{history_id}/playback
    ?use_agent=false        # Use agent for missing prices (slower but accurate)
    ?use_interpolation=true # Interpolate remaining gaps
```

Returns:
- `frames[]` - Daily portfolio snapshots with prices
- `events[]` - Original portfolio events
- `data_quality` - Stats about data sources used
- `total_frames` - Number of daily frames

### Added - Token Usage Tracking (2026-01-10)

Track and display LLM token usage across sessions:

#### Usage Service (`api/services/usage.py`)
- **Real-time Tracking** - Captures prompt/completion tokens for every LLM call
- **Aggregation** - Tracks usage by day, model, and endpoint (chat, chat-search, chat-research)
- **Recent Calls** - Keeps last 100 calls with timing and speed metrics
- **Speed Metrics** - Calculates tokens/second for performance monitoring

#### API Endpoints
```
GET /api/chat/usage       - Full usage summary with aggregations
GET /api/chat/usage/daily - Daily breakdown for last N days
```

#### Dashboard Integration
- **Status Bar** - Shows today's token count (click for details)
- **Usage Modal** - Displays today/all-time totals, by-model breakdown, recent calls
- **Speed Display** - Shows average tokens/second generation speed

### Fixed - Memory Summary Stripping (2026-01-10)
- Improved regex pattern for extracting LLM memory summaries
- Now handles various model output formats (multiline JSON, different bracket styles)
- User responses no longer include raw `[MEMORY_SUMMARY]` blocks

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
