# Roadmap v2.0 - Architecture Simplification

Based on the self-reflection analysis in `ARCHITECTURE_REVIEW.md`, this roadmap outlines the tasks for v2.0.

---

## Phase 1: Consolidate Services (Low Risk)

### Task 1a: Merge Reality Services
**Files to merge:**
- `api/services/alt_history.py`
- `api/services/alternate_reality.py`
- `api/services/reality_projections.py`

**Target:** `core/realities.py`

**Subagent prompt:**
```
Merge the three alternate reality/projection services into a single consolidated module.
1. Create new directory: core/
2. Create core/realities.py with all functionality from:
   - api/services/alt_history.py (alternate history creation, modification)
   - api/services/alternate_reality.py (reality engine, comparison)
   - api/services/reality_projections.py (future projections, LLM analysis)
3. Remove duplicate code between files
4. Update all imports throughout the codebase
5. Delete the old service files
6. Run tests to verify functionality
```

### Task 1b: Merge Scanner Services
**Files to merge:**
- `api/services/options_scanner.py`
- `api/services/agent_scanner.py`

**Target:** `core/scanner.py`

**Subagent prompt:**
```
Merge options scanner services into a single module.
1. Create core/scanner.py with functionality from:
   - api/services/options_scanner.py (yfinance options chain, scoring)
   - api/services/agent_scanner.py (LLM-enhanced recommendations)
2. Remove duplicate code (both call yfinance options chains)
3. Keep agent_scanner's self-reflective prompts
4. Update all imports throughout the codebase
5. Delete the old service files
6. Run tests to verify functionality
```

---

## Phase 2: Simplify Routes (Medium Risk)

### Task 2a: Route Consolidation
**Current routes (18):**
```
alt_history.py, alt_reality.py, backup.py, cash.py, chat.py,
config.py, events.py, history.py, ideas.py, notifications.py,
options.py, prices.py, research.py, scanner.py, setup.py,
state.py, trades.py, web.py
```

**Target routes (6):**
```
portfolio.py  - state, holdings, prices
events.py     - all event types: trades, options, cash, dividends
realities.py  - alternate histories, projections, comparisons
ai.py         - chat, insights, scanner, recommendations
admin.py      - config, backup, setup
web.py        - template serving
```

**Subagent prompt:**
```
Consolidate route files from 18 to 6 with backwards-compatible redirects.
1. Create portfolio.py combining: state.py, prices.py
2. Update events.py to include: trades.py, options.py, cash.py
3. Create realities.py combining: alt_history.py, alt_reality.py, history.py
4. Create ai.py combining: chat.py, scanner.py, ideas.py, research.py
5. Create admin.py combining: config.py, backup.py, setup.py, notifications.py
6. Keep web.py as-is
7. Add redirect stubs in old route files
8. Update main.py router registrations
9. Update frontend API calls
10. Run full test suite
```

---

## Phase 3: Split Dashboard JS (Low Risk)

### Task 3a: Modularize main.js
**Current:** `dashboard/src/main.js` (7000+ lines)

**Target modules:**
```
main.js       - Entry point, imports, init (~200 lines)
scene.js      - Three.js scene setup, lighting, controls
planets.js    - Planet/holding visualization, animations
realities.js  - Multiverse/alternate timeline visualization
ui.js         - HUD, panels, popups, dialogs
api.js        - All fetch calls, WebSocket client
tracker.js    - Ticker tracking feature
```

**Subagent prompt:**
```
Refactor dashboard/src/main.js into ES6 modules.
1. Create dashboard/src/scene.js - Three.js scene, camera, renderer, controls
2. Create dashboard/src/planets.js - createPlanet, updatePlanets, planet animations
3. Create dashboard/src/realities.js - alternate reality pyramid, cluster view
4. Create dashboard/src/ui.js - HUD updates, panels, modals, settings
5. Create dashboard/src/api.js - fetchPortfolioState, WebSocket, all API calls
6. Create dashboard/src/tracker.js - ticker tracking, trackedTickers map
7. Update main.js to import and orchestrate modules
8. Keep Vite bundling, update vite.config.js if needed
9. Test all dashboard functionality
```

---

## Phase 4: Consolidate Data Layer (Higher Risk)

### Task 4a: Single Source of Truth
**Goal:** Make CSV the only writable source, SQLite as read-only cache

**Changes:**
1. All writes go to CSV only
2. SQLite syncs from CSV on startup
3. Remove direct SQLite writes
4. Add CSV locking for concurrent access

**Subagent prompt:**
```
Consolidate data layer to use CSV as single source of truth.
1. Audit all database.py writes - redirect to CSV functions
2. Create csv_writer.py with atomic file operations
3. Update sync_csv_to_db() to be the only SQLite write path
4. Add file locking to prevent concurrent CSV writes
5. Update backup/restore to only work with CSV
6. Remove SQLite from git tracking (regenerated from CSV)
7. Test data integrity through full workflow
```

---

## Additional v2.0 Tasks

### Fix Deprecation Warnings
- Update FastAPI `@app.on_event("startup/shutdown")` to use lifespan handlers
- Update any deprecated pandas/numpy calls

### Documentation
- Update CLAUDE.md with new structure
- Update README with simplified architecture
- Generate API documentation

---

## Success Metrics

| Metric | v1.0 | v2.0 Target |
|--------|------|-------------|
| Route files | 18 | 6 |
| Service files | 15 | 5 (in core/) |
| main.js lines | 7000+ | <500 (entry) |
| Duplicate code | ~20% | <5% |

---

## Migration Notes

- Keep backwards compatibility during migration
- Add deprecation warnings to old endpoints
- Maintain all existing functionality
- Tests must pass at each step
- Document breaking changes in CHANGELOG

---

*Created for trader-tracker v2.0 - 2026-01-12*
