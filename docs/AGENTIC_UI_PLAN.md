# Agentic Portfolio Experience - UI Enhancement Plan

## Current State Analysis

### Existing AI Integration Points
| Component | Location | Current Function |
|-----------|----------|------------------|
| Chat Panel | 3D Dashboard (bottom-right) | Reactive Q&A with portfolio context |
| Insights Panel | 3D Dashboard (bottom-left) | Dexter research, manual refresh |
| AI Insights | Events page modal | Post-hoc reasoning on past decisions |
| LLM Settings | Settings page + 3D panel | Provider configuration |

### Current Limitations
1. **Reactive Only** - AI only responds when asked
2. **No Proactive Alerts** - User must manually check for issues
3. **Manual Price Updates** - User clicks "Update Prices" button
4. **No Automated Actions** - AI suggests but never executes
5. **Siloed Insights** - Research separate from actionable UI
6. **No Memory** - Chat history not persisted between sessions

---

## Proposed Agentic Architecture

### Tier 1: Proactive Intelligence Layer

#### 1.1 Smart Notifications System
```
┌─────────────────────────────────────────────────────────┐
│                   NOTIFICATION HUB                       │
├─────────────────────────────────────────────────────────┤
│ ⚠️  RISK ALERT: BMNR put expires in 3 days             │
│     Strike: $31 | Current: $30.06 | Action needed?     │
│     [Review] [Roll Forward] [Let Expire] [Dismiss]     │
├─────────────────────────────────────────────────────────┤
│ 💰 OPPORTUNITY: RKLB up 15% this week                  │
│     Consider trimming? You noted profit-taking goal.   │
│     [Take Profit] [Hold] [Set Alert] [Dismiss]         │
├─────────────────────────────────────────────────────────┤
│ 📊 REBALANCE: PLTR now 25% of portfolio (target: 20%) │
│     Overweight by $12,500. Trim to target?             │
│     [Rebalance] [Adjust Target] [Ignore] [Dismiss]     │
└─────────────────────────────────────────────────────────┘
```

**Notification Types:**
- Option expiration warnings (7 days, 3 days, 1 day)
- Position concentration alerts
- Price movement alerts (configurable thresholds)
- Goal progress milestones (25%, 50%, 75%, 100% of YTD income)
- Tax-loss harvesting opportunities
- Fundstrat/market event reminders (from NOTE events)

#### 1.2 Auto-Price Updates with Smart Scheduling
- Market hours: Auto-update every 15 minutes
- Pre/post market: Auto-update every 30 minutes
- Closed: No updates (preserve API quota)
- WebSocket push to all connected clients
- Badge shows "live" vs "stale" price status

---

### Tier 2: Conversational Command Interface

#### 2.1 Natural Language Actions
Transform the chat from Q&A to action-capable:

```
User: "Sell half my RKLB position"
Agent: I'll prepare that trade for you:
       - Sell 657 shares of RKLB @ $84.85 (market)
       - Estimated proceeds: $55,746
       - Estimated gain: $27,873 (based on cost basis)

       [Execute Trade] [Modify] [Cancel]
```

```
User: "Open a covered call on TSLA"
Agent: Based on your 372 TSLA shares, you can write up to 3 contracts.

       Suggested setup (30-45 DTE):
       - TSLA Feb 21 $480 Call
       - Premium: ~$1,200/contract
       - Max income: $3,600

       [Open 1 Contract] [Open 3 Contracts] [Customize] [Cancel]
```

```
User: "What should I do about my BMNR put?"
Agent: Your BMNR $31 put expires Jan 30 (20 days).

       Current status:
       - Stock: $30.06 (slightly below strike)
       - Premium collected: $4,000
       - Assignment risk: MODERATE

       Options:
       1. Let expire (keep premium if OTM at expiry)
       2. Roll to Feb $30 put (~$350 credit)
       3. Close now (~$200 cost, keep $3,800)

       Based on your thesis note from Jan 3: "BMNR thesis strong"
       Recommendation: Roll forward to maintain exposure.

       [Roll to Feb] [Close Position] [Let Ride] [Remind Me Later]
```

#### 2.2 Command Shortcuts
| Command | Action |
|---------|--------|
| `/buy TSLA 10` | Quick buy form pre-filled |
| `/sell RKLB 50%` | Sell half position |
| `/roll BMNR` | Option roll wizard |
| `/status` | Portfolio snapshot |
| `/alerts` | View active notifications |
| `/goals` | Income goal progress |

---

### Tier 3: Agent Workflows

#### 3.1 Workflow Templates
Pre-built multi-step automations:

**Monthly Income Review**
```
1. Fetch latest prices
2. Calculate YTD income vs goal
3. Identify expiring options (next 30 days)
4. Suggest roll/close actions
5. Identify new premium opportunities
6. Generate summary report
```

**Pre-Market Prep**
```
1. Fetch pre-market prices
2. Check overnight news (if news API integrated)
3. Review today's option expirations
4. Flag positions with >5% overnight moves
5. Summarize in notification
```

**Tax Optimization Scan**
```
1. Calculate unrealized gains/losses per position
2. Identify tax-loss harvesting candidates
3. Check wash sale implications
4. Suggest optimal lots to sell
5. Estimate tax impact
```

#### 3.2 Scheduled Agents
| Schedule | Agent | Action |
|----------|-------|--------|
| 9:25 AM ET | Pre-Market Agent | Prices + alerts |
| 4:05 PM ET | Close Agent | EOD summary + tomorrow prep |
| Monday 9 AM | Weekly Review Agent | Week-ahead outlook |
| 1st of Month | Monthly Agent | Income progress + rebalance check |

---

### Tier 4: UI Components

#### 4.1 Agent Command Center (New Page: `/agent`)
```
┌─────────────────────────────────────────────────────────────────────┐
│  🤖 AGENT COMMAND CENTER                              [Settings ⚙️] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │ 📊 STATUS       │  │ 🔔 NOTIFICATIONS│  │ 🎯 GOALS        │     │
│  │                 │  │                 │  │                 │     │
│  │ Portfolio: $1M  │  │ 3 Active Alerts │  │ YTD: $10,203    │     │
│  │ Cash: $73,749   │  │ 1 Urgent        │  │ Goal: $30,000   │     │
│  │ Prices: LIVE 🟢 │  │                 │  │ Progress: 34%   │     │
│  │                 │  │ [View All]      │  │ [Update Goal]   │     │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘     │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ 💬 AGENT CHAT                                                 │ │
│  │                                                               │ │
│  │ Agent: Good morning! Here's your pre-market brief:           │ │
│  │        - TSLA up 2.3% pre-market ($455)                      │ │
│  │        - Your BMNR put is now ITM ($30.06 < $31 strike)      │ │
│  │        - No options expiring this week                        │ │
│  │                                                               │ │
│  │        Would you like me to prepare a roll order for BMNR?   │ │
│  │                                                               │ │
│  │ [Yes, roll to Feb] [Show me options] [Not now]               │ │
│  │                                                               │ │
│  │ ┌─────────────────────────────────────────────────────────┐  │ │
│  │ │ Type a message or command...                      [Send]│  │ │
│  │ └─────────────────────────────────────────────────────────┘  │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ 📋 PENDING ACTIONS                                            │ │
│  │                                                               │ │
│  │ ☐ Review BMNR put (expires Jan 30)          [Execute] [Skip] │ │
│  │ ☐ Consider RKLB profit-taking (+52%)        [Execute] [Skip] │ │
│  │ ☐ Monthly income review due                 [Run Now] [Skip] │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │ 🤖 SCHEDULED AGENTS                                           │ │
│  │                                                               │ │
│  │ Pre-Market Brief     9:25 AM ET    [On ✓]   Next: Tomorrow   │ │
│  │ EOD Summary          4:05 PM ET    [On ✓]   Next: Today      │ │
│  │ Weekly Review        Mon 9 AM      [Off]    [Enable]         │ │
│  │ Monthly Income       1st of Month  [On ✓]   Next: Feb 1      │ │
│  └───────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

#### 4.2 Enhanced Notification Toast (All Pages)
```
┌──────────────────────────────────────────────────────────┐
│ 🔔 Agent Alert                                     [×]   │
│                                                          │
│ BMNR approaching strike price ($30.06 / $31)            │
│                                                          │
│ [Review Position]  [Snooze 1 Day]  [Dismiss]            │
└──────────────────────────────────────────────────────────┘
```

#### 4.3 Status Bar Enhancement (All Pages)
```
┌─────────────────────────────────────────────────────────────────────┐
│ [Logo] Dashboard | Events | Trade | Options | Cash | 🤖 Agent      │
│                                                                     │
│                    Prices: LIVE 🟢 | Alerts: 3 🔴 | [Update Prices] │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Foundation (Backend)
- [ ] WebSocket notification system
- [ ] Background task scheduler (APScheduler or Celery)
- [ ] Notification storage (SQLite table)
- [ ] Auto price update service
- [ ] Alert rule engine

### Phase 2: Notification UI
- [ ] Notification bell icon in navbar
- [ ] Notification dropdown/panel
- [ ] Toast notifications with actions
- [ ] Notification preferences page

### Phase 3: Enhanced Chat
- [ ] Action-capable chat responses
- [ ] Confirmation modals for actions
- [ ] Command shortcuts (/buy, /sell, etc.)
- [ ] Persistent conversation history

### Phase 4: Agent Command Center
- [ ] New `/agent` page
- [ ] Pending actions queue
- [ ] Scheduled agent configuration
- [ ] Workflow templates

### Phase 5: Scheduled Agents
- [ ] Pre-market brief agent
- [ ] EOD summary agent
- [ ] Option expiration monitor
- [ ] Goal progress tracker

---

## Technical Considerations

### Backend Requirements
```python
# New API routes needed
POST /api/agent/execute      # Execute agent action
GET  /api/notifications      # Get user notifications
POST /api/notifications/dismiss/{id}
GET  /api/agent/scheduled    # Get scheduled agents
POST /api/agent/scheduled    # Update schedule
POST /api/chat/action        # Chat with action capability
```

### New Database Tables
```sql
-- Notifications
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY,
    type TEXT NOT NULL,          -- 'alert', 'opportunity', 'reminder'
    severity TEXT DEFAULT 'info', -- 'info', 'warning', 'urgent'
    title TEXT NOT NULL,
    message TEXT,
    data_json TEXT,              -- Action context
    created_at TEXT,
    dismissed_at TEXT,
    snoozed_until TEXT
);

-- Agent Schedules
CREATE TABLE agent_schedules (
    id INTEGER PRIMARY KEY,
    agent_type TEXT NOT NULL,    -- 'pre_market', 'eod', 'weekly', 'monthly'
    cron_expression TEXT,
    enabled INTEGER DEFAULT 1,
    last_run TEXT,
    next_run TEXT,
    config_json TEXT
);

-- Pending Actions
CREATE TABLE pending_actions (
    id INTEGER PRIMARY KEY,
    action_type TEXT NOT NULL,   -- 'trade', 'roll_option', 'close_option'
    description TEXT,
    data_json TEXT,              -- Pre-filled action data
    suggested_by TEXT,           -- 'agent', 'notification', 'chat'
    created_at TEXT,
    executed_at TEXT,
    skipped_at TEXT
);
```

### WebSocket Events
```javascript
// Server -> Client
{ type: 'price_update', data: { prices: {...}, portfolio_change: 150 } }
{ type: 'notification', data: { id: 1, title: '...', severity: 'warning' } }
{ type: 'agent_complete', data: { agent: 'pre_market', summary: '...' } }

// Client -> Server
{ type: 'dismiss_notification', id: 1 }
{ type: 'execute_action', action_id: 5 }
{ type: 'snooze_notification', id: 1, until: '2026-01-11T09:00:00' }
```

---

## Priority Recommendation

**Start with Phase 1 + 2** (Notifications) - highest immediate value:
1. Users get proactive alerts without checking manually
2. Option expiration warnings prevent missed deadlines
3. Foundation enables all future agent features

**Quick Wins:**
- Auto price updates during market hours
- Option expiration countdown in UI
- Simple notification bell with count badge

---

## Questions for User

1. Which notification types are highest priority?
2. Should agent actions require confirmation or allow auto-execute for some?
3. Preferred notification delivery: in-app only, or also email/SMS?
4. Any specific scheduled reports needed beyond the suggested ones?
