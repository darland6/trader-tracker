# AI Agent Integration - Event-Sourced Financial System

## 🎯 Overview

Your financial planning system is now **AI-ready** with structured reason codes on every event. Feed your complete decision history into a custom AI agent for powerful analysis, pattern recognition, and strategic recommendations.

---

## 📊 System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│           CANONICAL EVENT LOG (with REASON field)             │
│                  event_log_enhanced.csv                       │
│                                                               │
│  Every decision logged with:                                  │
│  • What happened (data)                                       │
│  • Why it happened (reason)                                   │
│  • Strategic alignment                                        │
│  • Confidence level                                           │
│  • Your analysis                                              │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ↓
┌──────────────────────────────────────────────────────────────┐
│              PREPARE FOR AI AGENT                             │
│            prepare_for_agent.py                               │
│                                                               │
│  Converts log into structured JSON                            │
│  Adds portfolio & market context                              │
│  Performs reason pattern analysis                             │
└───────────────────────┬──────────────────────────────────────┘
                        │
                        ↓
┌──────────────────────────────────────────────────────────────┐
│                   AI AGENT (Claude/GPT)                       │
│              ai_agent_prompt.md                               │
│                                                               │
│  Analyzes patterns, provides insights                         │
│  Learns from your decisions                                   │
│  Recommends optimizations                                     │
│  Flags potential mistakes                                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 🔧 Complete File Set

### Core Event Log Files
1. **event_log_enhanced.csv** - Your canonical log with reason field
2. **starting_state.json** - Initial portfolio state
3. **reason_taxonomy.json** - Structured reason definitions

### AI Agent Files
4. **ai_agent_prompt.md** - Complete system prompt for AI
5. **prepare_for_agent.py** - Convert log to AI-ready JSON
6. **reconstruct_state.py** - Rebuild state from events

### Documentation
7. **README_Event_Sourcing.md** - Event sourcing concepts
8. **README_AI_Agent_Integration.md** - This file

---

## 🎯 Enhanced Event Structure

Every event now includes a **structured reason field**:

```json
{
  "event_id": 2,
  "timestamp": "2026-01-06 10:00:00",
  "event_type": "OPTION_OPEN",
  "data": {
    "ticker": "BMNR",
    "strategy": "Secured Put",
    "strike": 31.00,
    "premium": 4000
  },
  "reason": {
    "primary": "INCOME_GENERATION",
    "secondary": "WILLING_TO_BUY",
    "strategic_alignment": "STRATEGY_EXECUTION",
    "confidence": "HIGH",
    "timeframe": "SHORT_TERM",
    "analysis": "BMNR thesis strong (ETH financials). $31 is good entry if assigned."
  },
  "notes": "Collect monthly premium - part of wheel strategy",
  "tags": ["options", "income", "bmnr", "secured_put"],
  "affects_cash": true,
  "cash_delta": 4000
}
```

---

## 📋 Reason Taxonomy

### Trade Reasons

**BUY:**
- VALUE_OPPORTUNITY, DIP_BUYING, POSITION_BUILDING
- CONVICTION_INCREASE, DIVERSIFICATION, CATALYST_EXPECTED
- TECHNICAL_SIGNAL, REBALANCING, OTHER

**SELL:**
- PROFIT_TAKING, RISK_REDUCTION, REBALANCING
- CONVICTION_DECREASE, CASH_NEEDED, TAX_LOSS_HARVESTING
- STOP_LOSS, OPTION_ASSIGNMENT, BETTER_OPPORTUNITY, OTHER

### Option Reasons

**OPEN:**
- INCOME_GENERATION, DOWNSIDE_PROTECTION, WILLING_TO_BUY
- WILLING_TO_SELL, VOLATILITY_PLAY, PORTFOLIO_HEDGE, OTHER

**CLOSE:**
- PROFIT_TARGET_HIT, RISK_INCREASE, ROLL_OPPORTUNITY
- AVOID_ASSIGNMENT, VOLATILITY_CHANGE, OTHER

### Strategic Alignment
- GOAL_ALIGNMENT, STRATEGY_EXECUTION, MARKET_CONDITIONS
- LEARNING, THESIS_VALIDATION, RISK_MANAGEMENT
- OPPORTUNITY_COST, EMOTIONAL_DECISION, MISTAKE_CORRECTION

---

## 🚀 Quick Start - AI Agent

### Step 1: Prepare Your Data

```bash
python prepare_for_agent.py
```

This generates `agent_context.json` with:
- All events with reasons
- Current portfolio state
- Goals and progress
- Investment theses
- Market context

### Step 2: Load AI Agent Prompt

Copy contents of `ai_agent_prompt.md` into your AI agent system prompt.

### Step 3: Feed Context to Agent

```
You: [Paste agent_context.json]

Analyze my event log and tell me:
1. Am I following my strategy?
2. Which reasons lead to best outcomes?
3. Should I modify my PROFIT_TAKING approach?
```

---

## 🤖 AI Agent Capabilities

### 1. Pattern Recognition

**Example Query:**
```
"How have my INCOME_GENERATION options performed?"
```

**AI Response:**
```
Analyzing all OPTION_OPEN events with reason='INCOME_GENERATION':

Total: 12 events
Premium Collected: $45,200
Success Rate: 91.7% (11/12 expired worthless)

Best Performers:
- BMNR secured puts: $18,500 (4 events, 100% success)
- SPOT covered calls: $12,200 (3 events, 100% success)

Insight: All HIGH confidence events succeeded (8/8)
Recommendation: Continue current strategy, focus on HIGH conviction plays
```

### 2. Decision Quality Analysis

**Example Query:**
```
"Am I selling winners too early?"
```

**AI Response:**
```
SELL events with reason='PROFIT_TAKING':
- Average gain at sale: +42%
- Price 30 days later: +18% above sale
- Conclusion: Leaving ~15% on table

Pattern: You sell full position at 40-50% gains
Recommendation: Sell 50%, hold 50% with trailing stop
Expected Improvement: +15% annual return
```

### 3. Strategy Alignment Check

**Example Query:**
```
"Am I on track for my $30k income goal?"
```

**AI Response:**
```
Goal: $30,000 annual income via options + trading

Progress Analysis:
✅ YTD Income: $28,400 (95% of goal)
✅ INCOME_GENERATION events: 15
✅ Monthly avg: $3,553 (exceeds $2,500 target)
✅ Strategy alignment: 89% of events

Deviation Detected:
⚠️  3 EMOTIONAL_DECISION events (all losses: -$2,100)

Recommendation: Implement 24-hour rule for non-strategic trades
```

### 4. Predictive Recommendations

**Example Query:**
```
"BMNR put expires 1/30. What should I do?"
```

**AI Response:**
```
Context Analysis:
- BMNR: 8150 shares, thesis="ETH financials" (HIGH conviction)
- Open put: $31 strike, expires 1/30
- Current: $31.12 (slightly ITM)

Historical Pattern:
- You've rolled BMNR puts 3x before
- Each time: INCOME_GENERATION + WILLING_TO_BUY
- Average premium: $3,800
- Never been assigned (100% success)

Market Context:
- Correction expected in 6-8 weeks (Fundstrat)
- You're raising cash (PLTR, RKLB sells)

Recommendation:
Action: Roll to Feb, $32 strike
Primary Reason: INCOME_GENERATION
Secondary: WILLING_TO_BUY
Expected Premium: $3,500-4,000
Confidence: HIGH
Rationale: $32 still good entry if assigned during correction
```

---

## 💻 Usage Examples

### Analyze Reason Patterns

```bash
python prepare_for_agent.py --reason-analysis
```

Output:
```json
{
  "reason_distribution": {
    "INCOME_GENERATION": 15,
    "PROFIT_TAKING": 8,
    "RISK_REDUCTION": 5,
    "CASH_NEEDED": 3
  },
  "confidence_distribution": {
    "HIGH": 22,
    "MEDIUM": 7,
    "LOW": 2
  },
  "patterns": [
    {
      "pattern": "INCOME_GENERATION",
      "count": 15,
      "total_generated": 45200,
      "average_per_event": 3013.33
    },
    {
      "pattern": "HIGH_CONFIDENCE_DECISIONS",
      "count": 22,
      "net_cash_impact": 52400
    }
  ]
}
```

### Filter by Ticker

```bash
python prepare_for_agent.py --ticker TSLA
```

Generates AI context with only TSLA-related events.

### Filter by Date

```bash
python prepare_for_agent.py --since "2025-12-01"
```

Only events since December 1st.

---

## 🎓 Sample AI Agent Conversations

### Conversation 1: Learning from Patterns

**You:** Analyze all my SELL events. What patterns do you see?

**AI Agent:**
```
SELL Event Analysis (13 total):

Reason Distribution:
- PROFIT_TAKING: 8 events (62%)
- RISK_REDUCTION: 3 events (23%)
- CASH_NEEDED: 2 events (15%)

Success Patterns:

1. PROFIT_TAKING Events:
   Average Confidence: HIGH (6/8)
   Average Gain: +42%
   Average Hold Time: 73 days
   Pattern: You sell after sharp moves (+35-50% gains)
   
   Issue Detected: Stock continues +18% avg after sale
   Your Psychology: You value certainty over max gains
   
   Recommendation:
   - Sell 50-75% on PROFIT_TAKING
   - Hold remainder with 20% trailing stop
   - Tag as "CONVICTION_HOLD"

2. CASH_NEEDED Events:
   Always Precede: INCOME_GENERATION options (100%)
   Time Delta: Average 2 days before option
   
   Pattern Recognition:
   "CASH_NEEDED → INCOME_GENERATION" is your workflow
   This is systematic, not reactive
   
   Validation: ✓ Strategic, well-executed

3. RISK_REDUCTION Events:
   Timing: During market uncertainty
   Confidence: MEDIUM (all 3)
   Outcome: 2 saved money, 1 sold too early
   
   Recommendation: Increase confidence threshold
   Only execute RISK_REDUCTION with HIGH confidence
```

### Conversation 2: Strategy Optimization

**You:** Should I change my wheel strategy?

**AI Agent:**
```
Wheel Strategy Analysis:

Current Approach (from event log):
1. Sell secured puts (WILLING_TO_BUY prices)
2. Collect premium → INCOME_GENERATION
3. If assigned → hold and sell covered calls
4. Rinse and repeat

Performance Metrics:
- Total Premium: $45,200
- Win Rate: 91.7% (33/36 options)
- Average Premium: $1,256/option
- Annualized: $30,144 (exceeds $30k goal ✓)

What's Working:
✅ HIGH confidence puts: 100% success (12/12)
✅ WILLING_TO_BUY strikes: Smart entries
✅ Strategic alignment: 95%
✅ Risk management: Excellent

What Could Improve:
⚠️  You're not using covered calls enough
   - Only 4 covered call events
   - Your long stock should work harder
   - Additional income opportunity

Recommendations:
1. Keep Secured Puts (working perfectly)
2. Add Covered Calls on existing positions
   - BMNR: 8150 shares → Sell 81 calls monthly
   - TSLA: 367 shares → Sell 3-4 calls
   - Potential: +$8-12k annual premium
3. Roll strategy when:
   - IV > 30% (volatility play)
   - 21-30 DTE (optimal theta decay)
   - Strikes: 10-15% OTM (WILLING_TO_SELL)

Expected Improvement:
- Current: $30k/year
- With Covered Calls: $38-42k/year
- Risk Level: LOW (you own the stock)
- Alignment: STRATEGY_EXECUTION ✓
```

---

## 🔍 Advanced Analysis Queries

### Query: "What are my emotional decisions costing me?"

```
EMOTIONAL_DECISION Event Analysis:

Found: 3 events tagged EMOTIONAL_DECISION

Event #47: BUY TSLA (2025-11-23)
- Reason: FOMO after +12% day
- Confidence: LOW (you knew it!)
- Bought: 10 shares @ $445
- Outcome: -$892 (sold 2 weeks later @ $356)
- Lesson: "Chasing momentum = loss"

Event #58: SELL RKLB (2025-12-02)
- Reason: Panic during -8% day
- Confidence: MEDIUM
- Sold: 200 shares @ $72
- Current Price: $83.29
- Missed Gains: $2,258
- Lesson: "Don't sell conviction during volatility"

Event #61: BUY PLTR (2025-12-15)
- Reason: "Everyone's talking about it"
- Confidence: LOW
- Bought: 100 shares @ $178
- Outcome: -$320 (trim for cash @ $175)
- Lesson: "Social proof ≠ investment thesis"

Total Cost of Emotions: -$3,470

Recommendations:
1. Implement 24-hour rule for buys
2. Written thesis required (300+ words)
3. Never trade during market hours
4. If confidence = LOW → Don't trade
5. Track EMOTIONAL vs SYSTEMATIC outcomes monthly

Your systematic (HIGH confidence) trades: +$52,400
Your emotional (LOW confidence) trades: -$3,470

Conclusion: Trust your system, ignore emotions
```

---

## 📈 AI Agent Best Practices

### 1. Always Provide Context

Good query:
```
"Here's my event log [paste JSON]. Should I roll my BMNR put?"
```

Better query:
```
"Context: [paste JSON]
Current: BMNR trading at $31.12
Put: $31 strike, expires 1/30
Goal: Generate consistent income

Question: Roll or let expire? Provide reasoning framework."
```

### 2. Ask for Structured Output

```
"Analyze my PROFIT_TAKING strategy and respond with:
1. Pattern analysis
2. Success rate
3. Improvement recommendations
4. Expected impact
5. Risk assessment"
```

### 3. Reference the Taxonomy

```
"Filter events where:
- reason.primary = 'INCOME_GENERATION'
- reason.confidence = 'HIGH'
- event_type = 'OPTION_OPEN'

Show me success rate and total premium."
```

### 4. Learn from History

```
"Find all times I've faced this situation before:
- BMNR put expiring ITM
- HIGH conviction on stock
- Market uncertainty

What did I do? What were outcomes?"
```

---

## 🎯 Integration Workflow

### Daily: Log Events

```bash
# Add trade to event log
echo "15,2026-01-09 10:30:00,TRADE,..." >> event_log_enhanced.csv
```

### Weekly: Check Progress

```bash
# Generate agent context
python prepare_for_agent.py

# Ask AI agent:
"Am I on track for my goals?"
```

### Monthly: Deep Analysis

```bash
# Full reason analysis
python prepare_for_agent.py --reason-analysis

# Ask AI agent:
"What patterns emerged this month?
What should I change?"
```

### Quarterly: Strategy Review

```bash
# Generate 3-month context
python prepare_for_agent.py --since "2025-10-01"

# Ask AI agent:
"Review my last quarter.
What's working? What's not?
Recommend strategy adjustments."
```

---

## 🎓 Learning from the AI Agent

The AI agent learns YOUR decision-making style by analyzing:

1. **Reason Patterns** - What motivates your decisions
2. **Confidence Levels** - When you're sure vs uncertain
3. **Outcomes** - What works for YOU specifically
4. **Timeframes** - Your planning horizons
5. **Strategic Alignment** - How well you execute plans

Over time, it becomes a personalized advisor that:
- Knows your blind spots
- Recognizes your successful patterns
- Catches your mistakes early
- Optimizes YOUR specific approach

---

## ✅ Current Status

Your event log now has:
- ✅ **4 events** with full reason structure
- ✅ Reason taxonomy defined
- ✅ AI agent prompt template
- ✅ Data preparation scripts
- ✅ Ready for AI consumption

Next: Add reason field to all historical events for complete analysis!

---

**The AI agent becomes more powerful as your event log grows. Every decision makes it smarter about YOUR investing style.**
