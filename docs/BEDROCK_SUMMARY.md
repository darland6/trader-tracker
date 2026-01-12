# BEDROCK - Data Layer Consolidation

**Status**: ✅ Complete (2026-01-12)
**Code Name**: BEDROCK
**Goal**: Make CSV the single source of truth for events, with SQLite as read-only cache

---

## Executive Summary

BEDROCK consolidates the data layer to eliminate accidental database-only writes and establish a clear hierarchy:

1. **CSV is authoritative** - All event writes go to `data/event_log_enhanced.csv`
2. **SQLite is a cache** - `portfolio.db` events table is rebuilt from CSV
3. **File locking prevents corruption** - `fcntl` locks ensure concurrent write safety
4. **Backward compatible** - Existing code continues to work

---

## What Was Done

### 1. Created `core/data.py` (New File)

Centralized data access layer with these functions:

| Function | Purpose |
|----------|---------|
| `append_event()` | Write new events to CSV with file locking |
| `update_event()` | Modify existing events in CSV |
| `delete_event()` | Remove events from CSV |
| `load_events()` | Read all events with optional JSON parsing |
| `get_event_by_id()` | Retrieve single event |
| `get_events()` | Query events with filters |
| `sync_to_cache()` | Rebuild SQLite from CSV |
| `calculate_cash_delta()` | Auto-calculate cash impact from event data |
| `compact_price_events()` | Remove duplicate price update events |

**File locking mechanism**:
```python
with csv_lock('w'):  # Exclusive lock for writes
    df = pd.read_csv(CSV_PATH)
    # ... make changes ...
    df.to_csv(CSV_PATH, index=False)
```

### 2. Updated `api/database.py`

- Added prominent documentation at top of file explaining CSV as source of truth
- Marked `update_event()`, `delete_event()`, `compact_price_events()` as DEPRECATED
- These functions now delegate to `core/data.py` internally
- Emphasized that `sync_csv_to_db()` is the ONLY way to populate events table
- SQLite functions for `price_cache` and `notifications` unchanged (those are OK to write to)

### 3. Updated `cli/events.py`

- Imports `append_event`, `get_next_event_id`, `load_events`, `sync_to_cache` from `core.data`
- `append_event()` delegates to core layer with file locking
- `get_option_by_id()`, `get_option_by_position_id()`, `get_active_options()`, `get_recent_events()` use `load_events()` instead of raw `pd.read_csv()`
- All event creation still works the same from external callers' perspective

### 4. Documentation

- Created `docs/DATA_LAYER_ARCHITECTURE.md` - Comprehensive architecture guide
- Updated `CHANGELOG.md` - Added BEDROCK section with before/after data flow
- Created this summary document

---

## Files Modified

| File | Change Type | Description |
|------|-------------|-------------|
| `core/data.py` | **NEW** | Centralized data access layer with file locking |
| `api/database.py` | **UPDATED** | Delegates event operations to core, marked as cache |
| `cli/events.py` | **UPDATED** | Uses core/data.py for all CSV operations |
| `docs/DATA_LAYER_ARCHITECTURE.md` | **NEW** | Architecture documentation |
| `docs/BEDROCK_SUMMARY.md` | **NEW** | This file |
| `CHANGELOG.md` | **UPDATED** | Added BEDROCK entry |

---

## Files Checked (No Changes Needed)

These files already use `cli/events.py` or `api/database.py` functions, which now delegate to `core/data.py`:

- `api/routes/trades.py` - Uses `cli.events.create_trade_event()`
- `api/routes/options.py` - Uses `cli.events.create_option_event()`
- `api/routes/events.py` - Uses `api.database.update_event()` (which delegates)
- `api/routes/cash.py` - Uses `cli.events.create_cash_event()`
- `api/routes/prices.py` - Uses `cli.events.create_price_update_event()`

No changes needed due to backward compatibility layer.

---

## Testing Results

All 43 E2E tests pass:

```bash
$ pytest tests/test_e2e_workflow.py -v
============================= test session starts ==============================
collected 43 items

tests/test_e2e_workflow.py::TestEventLogLoading::test_load_event_log_exists PASSED
tests/test_e2e_workflow.py::TestEventLogLoading::test_event_log_has_required_columns PASSED
... (41 more tests) ...
tests/test_e2e_workflow.py::TestSessionTrackingE2E::test_langsmith_status_endpoint PASSED

=============================== 43 passed, 4 warnings in 10.38s ========================
```

No breaking changes detected.

---

## Data Flow Comparison

### Before BEDROCK

```
┌─────────────┐
│ API Routes  │
└──────┬──────┘
       │
       ├─────────────────────┐
       │                     │
       ▼                     ▼
┌──────────────┐    ┌──────────────┐
│ cli/events   │    │ api/database │
└──────┬───────┘    └──────┬───────┘
       │                   │
       │ (no lock)         │ (mixed writes)
       ▼                   ▼
┌──────────────────────────────────┐
│  event_log_enhanced.csv          │
└──────────────────────────────────┘
       │
       │ sync_csv_to_db()
       ▼
┌──────────────────────────────────┐
│  portfolio.db (SQLite)           │
└──────────────────────────────────┘

PROBLEMS:
- Multiple write paths to CSV
- No file locking → race conditions
- SQLite could diverge from CSV
```

### After BEDROCK

```
┌─────────────┐
│ API Routes  │
└──────┬──────┘
       │
       ├─────────────────────┐
       │                     │
       ▼                     ▼
┌──────────────┐    ┌──────────────┐
│ cli/events   │    │ api/database │
└──────┬───────┘    └──────┬───────┘
       │                   │
       │ delegates          │ delegates
       └──────┬────────────┘
              ▼
       ┌──────────────┐
       │ core/data.py │  ← SINGLE ENTRY POINT
       └──────┬───────┘
              │
              │ (with fcntl lock)
              ▼
       ┌──────────────────────────────────┐
       │  event_log_enhanced.csv          │
       │  SOURCE OF TRUTH                 │
       └──────┬───────────────────────────┘
              │
              │ sync_to_cache()
              ▼
       ┌──────────────────────────────────┐
       │  portfolio.db (SQLite)           │
       │  READ-ONLY CACHE                 │
       └──────────────────────────────────┘

BENEFITS:
✅ Single write path through core/data.py
✅ File locking prevents corruption
✅ CSV is always authoritative
✅ SQLite can be rebuilt at any time
```

---

## Key Principles Established

1. **CSV is the source of truth** - If CSV and SQLite disagree, CSV wins
2. **SQLite is rebuildable** - Can delete `portfolio.db` and regenerate via `sync_csv_to_db()`
3. **No direct SQLite writes** - Events table populated only by `sync_csv_to_db()`
4. **File locking is mandatory** - All CSV writes use `csv_lock()` context manager
5. **Exceptions are explicit** - Only `price_cache`, `notifications`, `agent_schedules` tables can be written to directly

---

## Usage Examples

### Writing Events (Correct Way)

```python
from core.data import append_event, sync_to_cache

# Create new event
event_id = append_event(
    event_type="TRADE",
    data={"action": "BUY", "ticker": "TSLA", "shares": 10, "price": 445.0},
    reason={"primary": "GROWTH", "explanation": "Bullish"},
    notes="Buy signal",
    tags=["trade", "tsla"],
    affects_cash=True,
    cash_delta=-4450.0
)

# Sync to SQLite cache
sync_to_cache()
```

### Reading Events

```python
from core.data import load_events, get_event_by_id

# Load all events
df = load_events(parse_json=True)

# Get single event
event = get_event_by_id(42)
```

### Updating Events

```python
from core.data import update_event, sync_to_cache

# Update event
update_event(
    event_id=42,
    updates={"notes": "Updated note", "data": {"new": "value"}}
)

# Sync to cache
sync_to_cache()
```

---

## Future Enhancements

1. **Compression** - Archive old events to compressed CSV
2. **Versioning** - Git integration for event log
3. **Replication** - Multi-node synchronization
4. **Audit Trail** - Track who modified events
5. **Batch Writes** - Optimize bulk operations

---

## Rollback Plan (If Needed)

If issues arise, revert these commits:

1. Remove `core/data.py`
2. Restore original `api/database.py` (remove DEPRECATED markers)
3. Restore original `cli/events.py` (direct CSV writes)
4. Tests should still pass (backward compatible)

---

## Success Criteria

- ✅ All tests pass
- ✅ No breaking changes to API
- ✅ Clear documentation
- ✅ File locking implemented
- ✅ Single source of truth established

**BEDROCK is complete and production-ready.**
