# Dashboard Analytics Subagent Skill

## 🎯 What This Skill Does

Creates a **parallel subagent** that automatically monitors your financial analysis agent and improves dashboard visualizations when new insights are discovered.

### The Problem It Solves

When your financial AI agent analyzes your event log and discovers patterns like:
- "Your INCOME_GENERATION options have 91.7% success rate"
- "HIGH confidence trades win 78% of the time"
- "Emotional decisions cost you -$3,470"

...your dashboard should **automatically update** to visualize these insights!

### How It Works

```
Financial Agent Analyzes Events
       ↓
Finds Patterns & Makes Recommendations
       ↓
Dashboard Subagent Activates 🚀
       ↓
Identifies Missing Visualizations
       ↓
Designs New Charts
       ↓
Generates Enhanced Dashboard
       ↓
User Sees Insights Immediately!
```

## 📊 What Gets Added to Your Dashboard

When the subagent runs, it adds charts for:

1. **Reason Performance Analysis** - Bar chart showing P/L by reason type
2. **Confidence vs Outcome** - Scatter plot correlating confidence with returns
3. **Emotional vs Systematic** - Comparison of emotional vs high-confidence trades
4. **Strategic Alignment Gauge** - % of decisions aligned with FI goals
5. **Win Rate Summary** - Simple win/loss percentage
6. **Enhanced Income Timeline** - Color-coded by reason type

## 🚀 Usage

### Method 1: Standalone

```python
from dashboard_subagent import DashboardAnalyticsSubagent

# Initialize
subagent = DashboardAnalyticsSubagent(
    event_log_path='event_log_enhanced.csv',
    dashboard_script_path='generate_dashboard.py'
)

# Run after financial agent analysis
recommendations = {
    'reason_distribution': {'INCOME_GENERATION': 15},
    'confidence_outcomes': {'HIGH': {'success_rate': 78}},
    'emotional_decisions': 3
}

report = subagent.assess_and_improve(recommendations)

# View enhanced dashboard
print(f"New dashboard: {report['new_dashboard_path']}")
```

### Method 2: Integrated with Financial Agent

```python
def analyze_portfolio(event_log):
    # 1. Run financial analysis
    recommendations = financial_agent.analyze(event_log)
    
    # 2. Spawn dashboard subagent in parallel
    subagent = DashboardAnalyticsSubagent(
        event_log_path='event_log_enhanced.csv',
        dashboard_script_path='generate_dashboard.py'
    )
    
    dashboard_improvements = subagent.assess_and_improve(recommendations)
    
    # 3. Return both
    return {
        'financial_analysis': recommendations,
        'dashboard_improvements': dashboard_improvements
    }
```

### Method 3: Automatic Trigger

```python
# Set up automatic triggering
def on_event_log_update(new_events):
    # When event log changes, analyze and update dashboard
    recommendations = quick_analyze(new_events)
    
    if recommendations_are_significant(recommendations):
        spawn_dashboard_subagent(recommendations)
```

## 📁 Skill Contents

```
dashboard-analytics-subagent.skill
├── SKILL.md                     # Skill definition and workflow
├── scripts/
│   └── dashboard_subagent.py   # Implementation
├── references/
│   ├── chart_types.md          # Chart selection guide
│   └── layout_patterns.md      # Dashboard layout principles
```

## 🎨 Design Principles

The subagent follows professional data visualization best practices:

### 1. Data-Driven Insights
Every chart answers a specific question and supports decision-making.

### 2. Visual Hierarchy
- **Critical**: Large, prominent (portfolio value, goal progress)
- **Important**: Medium size (holdings, income)
- **Supporting**: Smaller (stats, breakdowns)

### 3. Actionability
Charts highlight:
- What needs attention (red)
- What's working well (green)
- What to do next (annotations)

### 4. Progressive Disclosure
- **Overview** first (high-level metrics)
- **Details** on demand (drill-down capability)
- **Context** when needed (explanatory notes)

## 🔍 Example Output

When you run the subagent, you get:

### Assessment Report
```
GAPS IDENTIFIED:
✅ Current dashboard has portfolio value ✓
✅ Current dashboard has income tracking ✓
⚠️  Missing: Reason-based performance breakdown
⚠️  Missing: Confidence analysis visualization
❌ Missing: Emotional decision tracking

RECOMMENDATIONS FROM AGENT:
- "INCOME_GENERATION options: 91.7% success"
  → Need chart showing this!
- "HIGH confidence: 78% win rate"
  → Need confidence correlation chart
```

### Implementation Summary
```
NEW CHARTS ADDED:
✅ Reason Performance (bar chart)
✅ Confidence vs Outcome (scatter plot)
✅ Strategic Alignment Gauge
✅ Emotional vs Systematic Comparison

ENHANCED CHARTS:
✅ Income timeline: Now color-coded by reason
✅ Portfolio value: Added event annotations

FILES MODIFIED:
- Generated: generate_dashboard_enhanced.png
```

## 🛠️ Technical Details

### Requirements
- Python 3.7+
- pandas
- matplotlib
- numpy

### Input Format
Event log must have `reason_json` field with structure:
```json
{
  "primary": "INCOME_GENERATION",
  "secondary": "WILLING_TO_BUY",
  "strategic_alignment": "STRATEGY_EXECUTION",
  "confidence": "HIGH",
  "timeframe": "SHORT_TERM",
  "analysis": "Detailed reasoning..."
}
```

### Output
- Enhanced dashboard PNG/PDF
- JSON report with gaps and improvements
- Changelog of modifications

## 💡 Use Cases

### Use Case 1: After Pattern Discovery
```
Financial agent discovers: "You sell RKLB too early"
→ Subagent adds chart showing RKLB post-sale performance
→ User sees visual evidence of pattern
```

### Use Case 2: Risk Management
```
Financial agent flags: "3 emotional decisions cost -$3,470"
→ Subagent adds emotional vs systematic comparison
→ User sees cost of emotions visually
```

### Use Case 3: Strategy Validation
```
Financial agent confirms: "89% strategic alignment"
→ Subagent adds alignment gauge
→ User tracks adherence to plan visually
```

## 🎯 Integration with Your System

This skill integrates with your event-sourced financial system:

```
Event Log (with reasons)
       ↓
Financial Agent analyzes patterns
       ↓
Dashboard Subagent activates
       ↓
Enhanced visualizations created
       ↓
Better decision-making
```

## 📊 Before & After

**Before (Original Dashboard):**
- Portfolio value over time
- Individual holdings
- Income timeline
- Allocation pie chart

**After (Enhanced Dashboard):**
- Everything from before PLUS:
- Reason performance breakdown
- Confidence correlation analysis
- Emotional vs systematic comparison
- Strategic alignment gauge
- Win rate summary
- Color-coded income sources

## 🔧 Customization

Extend the subagent by:

1. **Adding chart types** - Edit `_create_enhanced_dashboard()`
2. **Changing colors** - Modify color schemes in plotting functions
3. **Adjusting layout** - Update grid specification
4. **Adding interactivity** - Integrate Plotly for interactive charts

## 📚 Reference Documentation

See `references/` for:
- **chart_types.md** - When to use each visualization type
- **layout_patterns.md** - Dashboard layout best practices
- Color coding standards
- Responsive design guidelines

## ✨ Key Benefits

1. **Automatic** - No manual dashboard updates needed
2. **Intelligent** - Only adds relevant visualizations
3. **Parallel** - Doesn't slow down main analysis
4. **Professional** - Follows UI/UX best practices
5. **Actionable** - Focuses on decision support

## 🎓 Learning from Output

The subagent teaches you through visualization:
- See which reasons work best for YOU
- Understand YOUR confidence calibration
- Recognize YOUR emotional patterns
- Track YOUR strategic alignment

---

**Install this skill to let your dashboard automatically evolve as your financial agent discovers new insights!**
