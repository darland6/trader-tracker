# Event-Sourced Financial Planning System

## 🎯 Core Concept: Canonical Event Log

**The event log is your SINGLE SOURCE OF TRUTH.**

Every change to your portfolio - every trade, option, deposit, withdrawal, note, or thought - is recorded as an immutable, timestamped event. Your entire financial history can be reconstructed at ANY point in time by replaying these events.

---

## 📊 System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    CANONICAL EVENT LOG                       │
│                     (event_log.csv)                          │
│                                                              │
│  Every change is appended here with timestamp                │
│  NEVER edit past events - only append new ones              │
└──────────────┬──────────────────────────────────────────────┘
               │
               │ Replay events →
               ↓
┌──────────────────────────────────────────────────────────────┐
│              STATE RECONSTRUCTION ENGINE                      │
│            (reconstruct_state.py)                            │
│                                                              │
│  Replays all events to build current (or historical) state  │
└──────────────┬───────────────────────────────────────────────┘
               │
               ├─→ Generate Excel Views
               ├─→ Generate Dashboard Charts
               ├─→ Answer "What if?" questions
               └─→ Time travel to any date
```

---

## 📝 Event Types

Your system supports 13 event types:

| Event Type | Purpose | Affects Cash? |
|------------|---------|---------------|
| `TRADE` | Buy/sell stocks | ✅ Yes |
| `OPTION_OPEN` | Sell put/call | ✅ Yes (premium) |
| `OPTION_CLOSE` | Buy back option | ✅ Yes (cost) |
| `OPTION_EXPIRE` | Option expired worthless | ❌ No (already recorded) |
| `OPTION_ASSIGN` | Option assigned (shares purchased/sold) | ✅ Yes |
| `DIVIDEND` | Dividend received | ✅ Yes |
| `DEPOSIT` | Cash deposited | ✅ Yes |
| `WITHDRAWAL` | Cash withdrawn | ✅ Yes |
| `PRICE_UPDATE` | Market prices updated | ❌ No |
| `SPLIT` | Stock split | ❌ No (shares adjusted) |
| `NOTE` | General comment/thought | ❌ No |
| `GOAL_UPDATE` | Financial goal changed | ❌ No |
| `STRATEGY_UPDATE` | Strategy modified | ❌ No |

---

## 🚀 Quick Start

### View Current State

```bash
python reconstruct_state.py
```

Shows your complete portfolio state reconstructed from all events.

### View Historical State

```bash
python reconstruct_state.py --as-of "2025-12-31 23:59:59"
```

See exactly what your portfolio looked like on Dec 31, 2025.

### Filter by Ticker

```bash
python reconstruct_state.py --ticker TSLA
```

See all TSLA-related events and their impact.

---

## 📥 Adding Events

### Method 1: Direct Append to CSV

Open `event_log.csv` and add a new row at the end:

```csv
15,2026-01-09 10:30:00,TRADE,"{""action"": ""BUY"", ""ticker"": ""TSLA"", ""shares"": 10, ""price"": 425.50, ""total"": 4255.00}","Adding on dip - good entry",true,-4255.00
```

### Method 2: Python Helper (Coming Soon)

```bash
python add_event.py trade --action BUY --ticker TSLA --shares 10 --price 425.50 \
    --notes "Adding on dip - good entry"
```

### Method 3: Interactive Mode (Coming Soon)

```bash
python add_event.py
# Prompts you for details
```

---

## 🔍 Understanding Your Event Log

### Event Structure

Each event has:

1. **event_id** - Unique sequential ID
2. **timestamp** - When it happened (YYYY-MM-DD HH:MM:SS)
3. **event_type** - Type of event (TRADE, OPTION_OPEN, etc.)
4. **data_json** - Event-specific data as JSON
5. **notes** - Your thoughts/comments about this event
6. **affects_cash** - True if this changed cash balance
7. **cash_delta** - Amount cash changed (negative for outflows)

### Example Event (TRADE):

```csv
1,2026-01-05 14:30:00,TRADE,"{""action"": ""SELL"", ""ticker"": ""PLTR"", ""shares"": ""multiple"", ""price"": 0, ""total"": 5500, ""gain_loss"": 5500}","Sold for cash - balancing for secured puts",true,5500.00
```

Breakdown:
- ID 1
- Jan 5, 2026 at 2:30 PM
- TRADE event
- Sold PLTR for $5,500
- Notes: Why you did it
- Added $5,500 to cash

---

## 🎨 State Reconstruction Output

When you run `reconstruct_state.py`, you get:

```
💵 CASH: $74,705.00
📊 PORTFOLIO VALUE: $1,001,141.68
💰 TOTAL VALUE: $1,075,846.68

📈 HOLDINGS:
   BMNR   |    8,150 shares @ $   31.12 = $  253,628.00
   TSLA   |      367 shares @ $  434.98 = $  159,637.66
   ... (all holdings)

🎯 ACTIVE OPTIONS: 1
   BMNR Secured Put $31.00 exp 2026-01-30 - $4,000.00

💸 INCOME (YTD):
   Total Income:     $   10,203.00
   ├─ Trading Gains: $    6,203.00
   ├─ Options:       $    4,000.00
   └─ Dividends:     $        0.00

📝 INVESTMENT THESES:
   BMNR   - eth running the financials of the world
   TSLA   - optimus, marcohard, elon
   ... (all theses)

🎯 GOALS:
   [Latest goal and motivation]

⚙️  STRATEGIES:
   [Current strategy]

📊 STATISTICS:
   Events Processed: 14
   Unrealized Gains: $0.00
```

---

## 💡 Powerful Capabilities

### 1. Time Travel

```bash
# What was my portfolio worth on Thanksgiving?
python reconstruct_state.py --as-of "2025-11-28 00:00:00"

# What did I own on my birthday?
python reconstruct_state.py --as-of "2025-08-15 23:59:59"
```

### 2. Event Analysis

```bash
# All TSLA activity
python reconstruct_state.py --ticker TSLA

# See exactly when you bought, sold, and your thoughts
```

### 3. Audit Trail

Every event is immutable and timestamped:
- Tax purposes: "When did I buy this?"
- Performance review: "What was I thinking?"
- Learning: "Why did I make that trade?"

### 4. Recovery

Lost your Excel file? No problem:
```bash
python reconstruct_state.py
# Generates complete current state from log

python generate_views.py  # (Coming soon)
# Regenerates all Excel sheets
```

### 5. Undo (Sort Of)

Want to see portfolio without a trade?
1. Copy event_log.csv to event_log_backup.csv
2. Remove the event row
3. Reconstruct state
4. Restore backup when done

---

## 📂 File Structure

```
Financial_Planning_System/
├── event_log.csv                  ← YOUR CANONICAL LOG ⭐
├── starting_state.json            ← Initial portfolio state
├── reconstruct_state.py           ← State reconstruction engine
├── generate_dashboard.py          ← Create visual dashboard
├── Financial_Planning_v2.0.xlsx   ← Generated view (read-only)
└── snapshots/                     ← Optional monthly backups
    └── event_log_2026-01.csv
```

---

## 🔐 Backup Strategy

**Critical: The event log IS your data.**

### Daily Backup
```bash
cp event_log.csv backups/event_log_$(date +%Y%m%d).csv
```

### Weekly Backup
```bash
# Upload to cloud storage
cp event_log.csv ~/Dropbox/
cp event_log.csv ~/Google\ Drive/
```

### Git Version Control
```bash
git add event_log.csv
git commit -m "Updated portfolio: Added TSLA position"
git push
```

---

## 📊 Your Current Event Log

As of now, you have:

- **14 events** total
- **3 trades** (2 sells, 0 buys recorded with full details)
- **1 option** opened (BMNR secured put)
- **7 investment theses** captured
- **1 goal** documented
- **1 strategy** defined
- **3 events** affecting cash (+$10,203 total)

### Events Breakdown:
- NOTE: 8 events
- TRADE: 2 events
- OPTION_OPEN: 1 event
- GOAL_UPDATE: 1 event
- STRATEGY_UPDATE: 1 event
- PRICE_UPDATE: 1 event

---

## 🎯 Next Steps

### Immediate:
1. **Add cost basis** to `starting_state.json`
   - Fill in your purchase prices for each holding
   - This enables gain/loss calculations

2. **Add historical trades** to event log
   - Go back through your broker history
   - Append all past transactions
   - Include your thoughts/notes at the time

3. **Set up daily price updates**
   - Automate PRICE_UPDATE events
   - Track portfolio value over time

### Soon:
4. **Create add_event.py** helper
   - Make it easy to log new events
   - Validate event data
   - Auto-generate event IDs

5. **Build generate_views.py**
   - Regenerate Excel from event log
   - Keep Excel read-only
   - Event log is master

6. **Monthly snapshots**
   - Backup event log monthly
   - Create point-in-time snapshots
   - Track long-term trends

---

## 🤔 FAQ

**Q: What if I make a mistake in the event log?**  
A: Don't edit old events. Instead, add a correcting event. For example, if you logged wrong shares, add a NOTE event explaining the error and add the correct TRADE event.

**Q: Can I edit past events?**  
A: Technically yes, but don't. The immutability is the power. If you must, add a NOTE explaining why.

**Q: How do I handle stock splits?**  
A: Add a SPLIT event with the split ratio. Reconstruction engine will adjust shares.

**Q: What about dividends?**  
A: Add DIVIDEND events. They'll show in YTD income.

**Q: Can I see my portfolio from last year?**  
A: Yes! `python reconstruct_state.py --as-of "2025-01-01 00:00:00"`

**Q: What if my event_log.csv gets corrupted?**  
A: This is why backups are critical. Copy it daily to multiple locations.

**Q: How do I import my old trades?**  
A: Download CSV from your broker, write a script to convert each row to an event, append to log.

---

## ⚡ Power User Tips

1. **Use meaningful notes**
   - Future you will thank past you
   - "Why did I buy this?" is answered in the notes

2. **Consistent timestamps**
   - Use actual trade times when possible
   - Helps with accurate historical state

3. **Tag your events**
   - Add categories to NOTE events
   - Easy filtering later

4. **Version control**
   - Git commit after each day's events
   - Full history forever

5. **Monthly snapshots**
   - Copy event_log.csv to dated file
   - Quick rollback if needed

---

## 🎉 Benefits You Get

✅ **Complete audit trail** - Every decision documented  
✅ **Time travel** - See portfolio at any point in history  
✅ **Tax ready** - Full transaction history with dates  
✅ **Learning tool** - Review past decisions with notes  
✅ **Disaster recovery** - One CSV file = complete history  
✅ **Immutable** - Past never changes, only append  
✅ **Queryable** - Filter by ticker, date, event type  
✅ **Portable** - Just a CSV file  
✅ **Version controlled** - Git-friendly  
✅ **Future-proof** - Plain text, readable forever  

---

**The Event Log IS Your Financial History. Guard It Well. Back It Up Religiously.**
