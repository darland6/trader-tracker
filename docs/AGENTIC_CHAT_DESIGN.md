# Agentic Chat Package Design

## Vision

A self-contained, reusable agent system that provides:
1. **Conversational Interface** - Chat with context awareness
2. **Insight Generation** - Analyze events and generate reasoning
3. **Pattern Learning** - Extract and remember behavioral patterns
4. **Persistent Memory** - Remember across sessions
5. **Tool Use** - Search, research, and act on data

---

## Core Capabilities

### 1. Insight Generation (on-demand)

Instead of generating insights at event creation time, the agent generates them conversationally:

```
User: "Analyze my last TSLA trade"
Agent: [Searches event log] [Generates insight]
       "Your TSLA purchase on Jan 5th..."

       **Reasoning**: You bought during a 5% dip, consistent with
       your pattern of accumulating on weakness...

       **Future Advice**: Consider setting alerts at $420 for
       another accumulation opportunity...

       **Past Reflection**: Similar to your META buy in Nov 2025
       which resulted in 15% gain...
```

**Commands**:
- `[ANALYZE_EVENT: event_id or description]` - Deep analysis of specific event
- `[GENERATE_INSIGHTS: ticker or date range]` - Batch insight generation
- `[REFLECT: topic]` - Reflect on patterns around a topic

### 2. Pattern Learning (continuous)

The agent extracts patterns from:
- Direct conversation (user states preferences)
- Behavioral analysis (agent observes patterns in events)
- Explicit teaching (user corrects or confirms patterns)

**Pattern Categories**:
```python
PATTERN_CATEGORIES = {
    "trading_style": "How user trades (momentum, value, income)",
    "risk_tolerance": "How much risk user accepts",
    "position_sizing": "How user sizes positions",
    "timing_preference": "When user prefers to trade",
    "ticker_affinity": "Which tickers user gravitates toward",
    "strategy_preference": "Preferred options strategies",
    "goal_alignment": "How decisions align with income goal"
}
```

**Learning Triggers**:
```
User: "I prefer selling puts on tech stocks I'd be happy to own"
Agent: [LEARN_PATTERN: strategy_preference]
       "Noted! I'll remember you prefer cash-secured puts on
       tech stocks where assignment would be acceptable."
```

### 3. Memory Architecture

```
AgentMemory/
├── conversation_memories[]     # What was discussed
│   ├── timestamp
│   ├── summary
│   ├── intent
│   ├── key_facts[]
│   └── insights_generated[]    # NEW: track which insights came from this
│
├── learned_patterns[]          # Behavioral patterns
│   ├── pattern
│   ├── category
│   ├── confidence (0-1)
│   ├── evidence_count          # How many times observed
│   ├── last_confirmed
│   └── source                  # "observed" | "stated" | "inferred"
│
├── event_insights{}            # Cached insights by event_id
│   └── [event_id]: {reasoning, advice, reflection, generated_at}
│
├── ticker_notes{}              # Per-ticker accumulated knowledge
│   └── [ticker]: {thesis, patterns, history_summary}
│
└── user_preferences{}          # Explicit preferences
    └── [key]: {value, updated}
```

---

## Agent Commands (Internal)

The agent can use these commands in its responses:

| Command | Purpose | Example |
|---------|---------|---------|
| `[SEARCH_LOG: query]` | Search event history | `[SEARCH_LOG: ticker:TSLA type:OPTION]` |
| `[ANALYZE_EVENT: id]` | Generate deep insight | `[ANALYZE_EVENT: 45]` |
| `[LEARN_PATTERN: category]` | Save a learned pattern | `[LEARN_PATTERN: risk_tolerance]` |
| `[RESEARCH_QUERY: q]` | External financial research | `[RESEARCH_QUERY: TSLA Q4 earnings]` |
| `[UPDATE_TICKER_THESIS: ticker]` | Update thesis for ticker | `[UPDATE_TICKER_THESIS: META]` |
| `[MEMORY_SUMMARY]` | Save conversation memory | (auto-generated) |

---

## Package Structure

```
agent/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── agent.py              # Main AgentChat class
│   ├── memory.py             # AgentMemory class
│   ├── patterns.py           # PatternLearner class
│   └── insights.py           # InsightGenerator class
│
├── tools/
│   ├── __init__.py
│   ├── search.py             # Event log search
│   ├── research.py           # External research (Dexter)
│   └── calculator.py         # Financial calculations
│
├── prompts/
│   ├── __init__.py
│   ├── system.py             # System prompts
│   ├── insight.py            # Insight generation prompts
│   └── pattern.py            # Pattern extraction prompts
│
├── tracking/
│   ├── __init__.py
│   ├── session.py            # Session tracking (LangSmith)
│   └── usage.py              # Token usage tracking
│
├── api/
│   ├── __init__.py
│   └── router.py             # FastAPI router (pluggable)
│
└── ui/
    ├── components/           # Reusable HTML/JS
    └── static/               # CSS
```

---

## Integration API

```python
from agent import AgentChat, AgentMemory

# Initialize with project-specific context
agent = AgentChat(
    # Core config
    llm_config=my_llm_config,
    memory=AgentMemory(storage_path="data/agent_memory.json"),

    # Project-specific loaders
    get_state=lambda: build_portfolio_state(),
    get_events=lambda limit: get_all_events(limit),
    search_events=lambda q: search_event_log(q),

    # Optional tools
    tools=[
        DexterResearchTool(),
        OptionsCalculatorTool(),
    ],

    # Project context
    system_context="""
    This is a portfolio tracker focused on generating $30K/year income.
    The user trades options (primarily cash-secured puts) and stocks.
    """,

    # Pattern categories for this project
    pattern_categories=TRADING_PATTERN_CATEGORIES,
)

# Mount to FastAPI
app.include_router(agent.router, prefix="/api/chat")

# Or use directly
response = await agent.chat("Analyze my TSLA trades this month")
```

---

## Insight Generation Flow

```
User asks about event/trade
         │
         ▼
┌─────────────────────┐
│  Search Event Log   │ ◄── [SEARCH_LOG: ...]
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Load Portfolio     │ ◄── Current state for context
│  Context            │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Check Cached       │ ◄── Have we analyzed this before?
│  Insights           │
└──────────┬──────────┘
           │ (cache miss)
           ▼
┌─────────────────────┐
│  Generate Insight   │ ◄── LLM: reasoning + advice + reflection
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Cache Insight      │ ◄── Save to event_insights{}
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Extract Patterns   │ ◄── Did we learn something new?
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Return Response    │ ◄── With memory summary
└─────────────────────┘
```

---

## Pattern Learning Flow

```
Agent observes behavior OR user states preference
                    │
                    ▼
         ┌─────────────────────┐
         │  Pattern Extractor  │
         │  - Category?        │
         │  - Confidence?      │
         │  - Evidence?        │
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  Existing Pattern?  │
         └──────────┬──────────┘
                    │
        ┌───────────┴───────────┐
        ▼                       ▼
   [New Pattern]          [Update Existing]
        │                       │
        ▼                       ▼
   Add to memory          Increase confidence
   confidence=0.3         Add evidence
                          Update last_confirmed
                    │
                    ▼
         ┌─────────────────────┐
         │  Acknowledge to     │
         │  User (optional)    │
         └─────────────────────┘
```

---

## Example Interactions

### Insight Generation
```
User: "Why did I sell that BMNR put last week?"

Agent: Let me find that trade...
[SEARCH_LOG: ticker:BMNR type:OPTION date:2026-01]

Found your BMNR $31 put sold on Jan 8th for $400 premium.

**Reasoning**: You sold this put at a 12% OTM distance while BMNR
was showing strength. The $400 premium on a $3,100 collateral
requirement gives a 12.9% annualized return. This aligns with
your income generation goal.

**Future Advice**: BMNR has earnings on Feb 15th. Consider
closing before earnings if you've captured 50%+ of premium,
or be prepared for assignment if it drops.

**Past Reflection**: This is your 3rd BMNR put this quarter.
Previous ones expired worthless (Jan $28, Dec $26), suggesting
your strike selection has been conservative and effective.

[LEARN_PATTERN: ticker_affinity] Noting your recurring interest in BMNR.
```

### Pattern Confirmation
```
User: "I only sell puts on stocks I'd be happy to own long-term"

Agent: Got it! I've learned this about your trading style:

[LEARN_PATTERN: strategy_preference]
Pattern: "Only sells puts on stocks acceptable for long-term ownership"
Category: strategy_preference
Confidence: HIGH (directly stated)

I'll keep this in mind when analyzing your trades and suggesting
opportunities. This explains why you've avoided puts on meme stocks
despite their high premiums.
```

### Batch Insight Generation
```
User: "Generate insights for all my trades this month"

Agent: I'll analyze your January 2026 activity...
[SEARCH_LOG: date:2026-01]

Found 8 events. Generating insights...

1. **TSLA Buy (Jan 3)** - Accumulated during dip ✓
2. **BMNR Put Sold (Jan 8)** - Income generation ✓
3. **META Shares Sold (Jan 12)** - Profit taking at +18% ✓
...

**Monthly Patterns Observed**:
- You're more active in the first week of the month
- Average premium yield on puts: 14.2% annualized
- All put strikes were >10% OTM (conservative)

[LEARN_PATTERN: timing_preference] More active early in month
[LEARN_PATTERN: risk_tolerance] Prefers >10% OTM for puts
```

---

## Migration Path

1. **Phase 1**: Create `agent/` package structure
2. **Phase 2**: Move memory.py, usage.py, langsmith_tracing.py
3. **Phase 3**: Add InsightGenerator and PatternLearner
4. **Phase 4**: Update chat.py to use new agent
5. **Phase 5**: Add new commands to system prompt
6. **Phase 6**: Test and iterate

---

## Questions to Resolve

1. Should insights be written back to event_log CSV or kept separate?
2. How to handle conflicting patterns (user says one thing, does another)?
3. Should pattern learning require user confirmation?
4. How much historical context to include for insight generation?
