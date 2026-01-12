# Data Write Audit - Post-BEDROCK

**Audit Date**: 2026-01-12
**Purpose**: Document all files that write data and verify BEDROCK compliance

---

## ✅ Compliant Files (Write to CSV via core/data.py)

### Core Layer

| File | Functions | Data Store | Compliance |
|------|-----------|------------|------------|
| `core/data.py` | `append_event()`, `update_event()`, `delete_event()`, `compact_price_events()` | CSV (with file locking) | ✅ **SOURCE OF TRUTH** |

### CLI Layer

| File | Functions | Data Store | Compliance |
|------|-----------|------------|------------|
| `cli/events.py` | `append_event()`, `create_trade_event()`, `create_option_event()`, `create_option_close_event()`, `create_cash_event()`, `create_price_update_event()` | Delegates to `core/data.py` | ✅ Compliant |

### API Layer

| File | Functions | Data Store | Compliance |
|------|-----------|------------|------------|
| `api/database.py` | `update_event()` (DEPRECATED), `delete_event()` (DEPRECATED), `compact_price_events()` (DEPRECATED) | Delegates to `core/data.py` | ✅ Compliant (backward compat) |
| `api/routes/events.py` | `update_event_by_id()`, `recalculate_all_events()` | Uses `api.database` (which delegates) | ✅ Compliant |
| `api/routes/trades.py` | `execute_trade()` | Uses `cli.events.create_trade_event()` | ✅ Compliant |
| `api/routes/options.py` | `open_option()`, `close_option()` | Uses `cli.events` functions | ✅ Compliant |
| `api/routes/cash.py` | Cash operations | Uses `cli.events.create_cash_event()` | ✅ Compliant |
| `api/routes/prices.py` | `update_prices()` | Uses `cli.events.create_price_update_event()` | ✅ Compliant |

---

## ✅ Allowed Direct SQLite Writes (Non-Event Data)

These write to SQLite tables that are NOT part of the event log (approved exceptions):

### Price Cache

| File | Function | SQLite Table | Purpose |
|------|----------|--------------|---------|
| `api/database.py` | `update_price_cache()` | `price_cache` | Temporary stock price caching |
| `api/routes/prices.py` | Price updates | `price_cache` (via `update_price_cache()`) | Stock prices |

### Notifications

| File | Function | SQLite Table | Purpose |
|------|----------|--------------|---------|
| `api/database.py` | `create_notification()`, `dismiss_notification()`, `snooze_notification()` | `notifications` | System alerts |
| `api/routes/notifications.py` | Notification management | `notifications` (via database functions) | Alert queue |
| `api/services/alerts.py` | Alert generation | `notifications` (via database functions) | Portfolio alerts |

### Agent Schedules

| File | Function | SQLite Table | Purpose |
|------|----------|--------------|---------|
| `api/database.py` | Schedule management functions | `agent_schedules` | Background job schedules |

---

## 🔒 Read-Only SQLite Tables (Never Write Directly)

These SQLite tables are populated ONLY via `sync_csv_to_db()`:

| Table | Populated By | Source |
|-------|--------------|--------|
| `events` | `sync_csv_to_db()` | `data/event_log_enhanced.csv` |

**Rule**: NEVER insert/update/delete from `events` table directly. Use `core/data.py` to modify CSV, then sync.

---

## 🔍 Files That Read Data

### Read from CSV

| File | Function | Purpose |
|------|----------|---------|
| `core/data.py` | `load_events()` | Load all events with JSON parsing |
| `cli/events.py` | Various functions | Read events for display/processing |
| `reconstruct_state.py` | State reconstruction | Build portfolio state from events |
| `scripts/setup_portfolio.py` | Portfolio setup | Read/modify event log |

### Read from SQLite Cache

| File | Function | Purpose |
|------|----------|---------|
| `api/database.py` | `get_all_events()`, `get_event_by_id()` | Fast queries via cache |
| `api/routes/state.py` | State endpoints | Portfolio state queries |
| `api/routes/events.py` | Event endpoints | Event history queries |

---

## 📋 Data Flow Summary

```
┌─────────────────────────────────────────────────────────────┐
│                        WRITE PATH                            │
└─────────────────────────────────────────────────────────────┘

All Event Writes:
  API/CLI → core/data.py → CSV (with file lock) → sync_to_cache()

Price Cache Writes:
  api/routes/prices.py → api/database.update_price_cache() → SQLite.price_cache

Notification Writes:
  api/services/alerts.py → api/database.create_notification() → SQLite.notifications

┌─────────────────────────────────────────────────────────────┐
│                        READ PATH                             │
└─────────────────────────────────────────────────────────────┘

Events (Authoritative):
  core/data.load_events() → CSV

Events (Fast Queries):
  api/database.get_all_events() → SQLite.events (cache)

Prices:
  api/database.get_cached_prices() → SQLite.price_cache

Notifications:
  api/database.get_active_notifications() → SQLite.notifications
```

---

## 🔐 File Locking Details

All CSV writes in `core/data.py` use this pattern:

```python
with csv_lock('w'):  # Exclusive lock (LOCK_EX)
    df = pd.read_csv(CSV_PATH)
    # ... modifications ...
    df.to_csv(CSV_PATH, index=False)
```

Reads use shared locks:

```python
with csv_lock('r'):  # Shared lock (LOCK_SH)
    df = pd.read_csv(CSV_PATH)
```

Lock file: `data/event_log_enhanced.csv.lock`

---

## 🚫 Prohibited Patterns

### ❌ NEVER do this:

```python
# Direct SQLite event writes
conn = sqlite3.connect('portfolio.db')
cursor.execute("INSERT INTO events ...")  # ❌ BAD!

# CSV writes without locking
df = pd.read_csv('data/event_log_enhanced.csv')
df = pd.concat([df, new_row])
df.to_csv('data/event_log_enhanced.csv')  # ❌ NO LOCK!

# Direct CSV modification from routes
with open('data/event_log_enhanced.csv', 'a') as f:
    f.write('...')  # ❌ BYPASSES core/data.py!
```

### ✅ ALWAYS do this:

```python
# Use core/data.py for events
from core.data import append_event, sync_to_cache
event_id = append_event(...)
sync_to_cache()

# Use cli/events.py helpers
from cli.events import create_trade_event
event_id = create_trade_event(...)

# Use api/database for allowed SQLite writes
from api.database import update_price_cache
update_price_cache({'TSLA': 445.0})
```

---

## 📊 Write Operation Counts (Estimated)

Based on codebase analysis:

| Operation Type | Files | Daily Frequency | Goes Through core/data.py? |
|---------------|-------|-----------------|---------------------------|
| Event Creation | 5 | 10-50 | ✅ Yes |
| Event Update | 2 | 1-5 | ✅ Yes |
| Event Delete | 1 | 0-1 | ✅ Yes |
| Price Update | 1 | 5-20 | ✅ Yes (create_price_update_event) |
| Price Cache | 1 | 5-20 | ⚠️  Direct SQLite (allowed) |
| Notifications | 2 | 0-10 | ⚠️  Direct SQLite (allowed) |

**Compliance Rate**: 100% for event operations

---

## ✅ Verification Checklist

- [x] All event writes go through `core/data.py`
- [x] File locking implemented for CSV writes
- [x] SQLite events table is read-only (populated via sync only)
- [x] Price cache and notifications use SQLite directly (approved)
- [x] No direct CSV writes outside core/data.py
- [x] All tests pass
- [x] Backward compatibility maintained

**Status**: BEDROCK compliance verified ✅

---

## 🔄 Sync Operations

| Trigger | Function | Frequency |
|---------|----------|-----------|
| Module import | `init_database()` + `sync_csv_to_db()` | Once per process |
| After event write | `sync_to_cache()` | After each write |
| API startup | `sync_csv_to_db()` | Once per server start |
| Manual | `/api/events` endpoint with sync | On-demand |

---

## 📝 Audit Notes

1. **No violations found** - All event operations properly route through core layer
2. **Exceptions documented** - Price cache and notifications have clear justification
3. **Tests verify compliance** - All 43 E2E tests pass
4. **Documentation complete** - Architecture and usage guides created

**Next Audit**: Recommended after major feature additions
