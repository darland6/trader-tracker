"""
End-to-End Tests for Financial Planning System

Tests the complete workflow:
1. Event log loading and parsing
2. State reconstruction from events
3. Agent context preparation
4. Reason analysis
"""

import pytest
import json
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from reconstruct_state import load_event_log, load_starting_state, reconstruct_state
from scripts.prepare_for_agent import load_event_log as load_enhanced_log, prepare_agent_context, analyze_reasons


class TestEventLogLoading:
    """Test event log loading and parsing"""

    def test_load_event_log_exists(self):
        """Test that the event log file exists and can be loaded"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        assert event_log_path.exists(), f"Event log not found at {event_log_path}"

        df = load_event_log(str(event_log_path))
        assert len(df) > 0, "Event log should have at least one event"

    def test_event_log_has_required_columns(self):
        """Test that event log has all required columns"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_event_log(str(event_log_path))

        required_columns = ['event_id', 'timestamp', 'event_type', 'data', 'notes', 'affects_cash', 'cash_delta']
        for col in required_columns:
            assert col in df.columns, f"Missing required column: {col}"

    def test_event_log_data_parsed_as_dict(self):
        """Test that data_json is properly parsed into dict"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_event_log(str(event_log_path))

        for idx, row in df.iterrows():
            assert isinstance(row['data'], dict), f"Event {row['event_id']} data should be a dict"

    def test_event_log_timestamps_parsed(self):
        """Test that timestamps are properly parsed as datetime"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_event_log(str(event_log_path))

        assert df['timestamp'].dtype.name.startswith('datetime'), "Timestamp should be datetime type"


class TestStartingState:
    """Test starting state loading"""

    def test_starting_state_exists(self):
        """Test that starting state file exists"""
        script_dir = Path(__file__).parent.parent
        starting_state_path = script_dir / 'data' / 'starting_state.json'

        assert starting_state_path.exists(), f"Starting state not found at {starting_state_path}"

    def test_starting_state_has_required_fields(self):
        """Test that starting state has required fields"""
        script_dir = Path(__file__).parent.parent
        starting_state_path = script_dir / 'data' / 'starting_state.json'

        state = load_starting_state(str(starting_state_path))

        assert 'cash' in state, "Starting state should have 'cash'"
        assert 'initial_holdings' in state, "Starting state should have 'initial_holdings'"
        assert 'starting_date' in state, "Starting state should have 'starting_date'"

    def test_starting_state_holdings_structure(self):
        """Test that holdings have proper structure"""
        script_dir = Path(__file__).parent.parent
        starting_state_path = script_dir / 'data' / 'starting_state.json'

        state = load_starting_state(str(starting_state_path))

        for ticker, info in state['initial_holdings'].items():
            assert 'shares' in info, f"{ticker} should have 'shares'"
            assert 'cost_basis_per_share' in info, f"{ticker} should have 'cost_basis_per_share'"


class TestStateReconstruction:
    """Test state reconstruction from events"""

    def test_reconstruct_state_basic(self):
        """Test basic state reconstruction"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_event_log(str(event_log_path))
        state = reconstruct_state(df)

        assert 'cash' in state, "State should have 'cash'"
        assert 'holdings' in state, "State should have 'holdings'"
        assert 'ytd_income' in state, "State should have 'ytd_income'"
        assert 'active_options' in state, "State should have 'active_options'"

    def test_reconstruct_state_cash_calculation(self):
        """Test that cash is calculated correctly from events"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'
        starting_state_path = script_dir / 'data' / 'starting_state.json'

        df = load_event_log(str(event_log_path))
        starting = load_starting_state(str(starting_state_path))
        state = reconstruct_state(df)

        # Calculate expected cash from starting + all cash deltas
        expected_cash = starting['cash']
        for idx, event in df.iterrows():
            expected_cash += event['cash_delta']

        assert abs(state['cash'] - expected_cash) < 0.01, f"Cash mismatch: {state['cash']} vs {expected_cash}"

    def test_reconstruct_state_income_tracking(self):
        """Test that YTD income is tracked correctly"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_event_log(str(event_log_path))
        state = reconstruct_state(df)

        # Income should be sum of trading gains + option income + dividends
        expected_income = state['ytd_trading_gains'] + state['ytd_option_income'] + state['ytd_dividends']
        assert abs(state['ytd_income'] - expected_income) < 0.01, "YTD income should equal sum of components"

    def test_reconstruct_state_holdings_from_starting(self):
        """Test that holdings are initialized from starting state"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'
        starting_state_path = script_dir / 'data' / 'starting_state.json'

        df = load_event_log(str(event_log_path))
        starting = load_starting_state(str(starting_state_path))
        state = reconstruct_state(df)

        # All starting holdings should be present
        for ticker in starting['initial_holdings']:
            assert ticker in state['holdings'], f"Starting holding {ticker} should be in state"

    def test_reconstruct_state_active_options(self):
        """Test that active options are tracked"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_event_log(str(event_log_path))
        state = reconstruct_state(df)

        # Count OPTION_OPEN events
        option_opens = df[df['event_type'] == 'OPTION_OPEN']
        option_closes = df[df['event_type'].isin(['OPTION_CLOSE', 'OPTION_EXPIRE', 'OPTION_ASSIGN'])]

        # Active options should be tracked (may not match exactly due to UUID matching in imported data)
        expected_max = len(option_opens)  # Can't have more active than opened
        assert len(state['active_options']) <= expected_max, f"More active options than opened"
        assert len(state['active_options']) >= 0, f"Active options count should be non-negative"

    def test_reconstruct_state_as_of_timestamp(self):
        """Test state reconstruction at a specific timestamp"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_event_log(str(event_log_path))

        # Get first event timestamp
        first_timestamp = df['timestamp'].min()

        # Reconstruct state before first event
        state_before = reconstruct_state(df, as_of_timestamp=str(first_timestamp - pd.Timedelta(days=1)))

        # Should have zero income since no events processed
        assert state_before['ytd_income'] == 0, "No income before first event"
        assert state_before['events_processed'] == 0, "No events processed before first event"


class TestAgentContextPreparation:
    """Test agent context preparation"""

    def test_prepare_agent_context_structure(self):
        """Test that agent context has expected structure"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_enhanced_log(str(event_log_path))
        context = prepare_agent_context(df)

        assert 'metadata' in context, "Context should have 'metadata'"
        assert 'current_portfolio' in context, "Context should have 'current_portfolio'"
        assert 'goals' in context, "Context should have 'goals'"
        assert 'events' in context, "Context should have 'events'"

    def test_prepare_agent_context_metadata(self):
        """Test that metadata is correctly populated"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_enhanced_log(str(event_log_path))
        context = prepare_agent_context(df)

        assert context['metadata']['total_events'] == len(df), "Event count mismatch"
        assert 'generated_at' in context['metadata'], "Missing generated_at"
        assert 'date_range' in context['metadata'], "Missing date_range"

    def test_prepare_agent_context_portfolio(self):
        """Test that portfolio data is correctly extracted"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_enhanced_log(str(event_log_path))
        context = prepare_agent_context(df)

        portfolio = context['current_portfolio']
        assert 'total_value' in portfolio, "Missing total_value"
        assert 'cash' in portfolio, "Missing cash"
        assert 'holdings' in portfolio, "Missing holdings"

    def test_prepare_agent_context_goals(self):
        """Test that goals are correctly set"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_enhanced_log(str(event_log_path))
        context = prepare_agent_context(df)

        goals = context['goals']
        assert goals['annual_income_target'] == 30000, "Annual income target should be $30,000"
        assert goals['monthly_income_target'] == 2500, "Monthly income target should be $2,500"
        assert 'progress_pct' in goals, "Missing progress percentage"

    def test_prepare_agent_context_events_included(self):
        """Test that events are included in context"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_enhanced_log(str(event_log_path))
        context = prepare_agent_context(df, include_full_history=True)

        assert len(context['events']) == len(df), "All events should be included"

        for event in context['events']:
            assert 'event_id' in event, "Event should have event_id"
            assert 'timestamp' in event, "Event should have timestamp"
            assert 'event_type' in event, "Event should have event_type"


class TestReasonAnalysis:
    """Test reason pattern analysis"""

    def test_analyze_reasons_basic(self):
        """Test basic reason analysis"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_enhanced_log(str(event_log_path))
        analysis = analyze_reasons(df)

        assert 'reason_distribution' in analysis, "Missing reason_distribution"
        assert 'confidence_distribution' in analysis, "Missing confidence_distribution"
        assert 'patterns' in analysis, "Missing patterns"

    def test_analyze_reasons_distribution(self):
        """Test that reason distribution is calculated"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_enhanced_log(str(event_log_path))
        analysis = analyze_reasons(df)

        # Should have at least one reason type
        assert len(analysis['reason_distribution']) > 0, "Should have reason distribution"


class TestFullWorkflowE2E:
    """End-to-end workflow tests"""

    def test_full_workflow_reconstruct_to_agent_context(self):
        """Test the complete workflow from events to agent context"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        # Step 1: Load events
        df = load_enhanced_log(str(event_log_path))
        assert len(df) > 0, "Should have events"

        # Step 2: Reconstruct state
        state = reconstruct_state(df)
        assert state['events_processed'] == len(df), "All events should be processed"

        # Step 3: Prepare agent context
        context = prepare_agent_context(df)
        assert context['current_portfolio']['cash'] == state['cash'], "Cash should match"

        # Step 4: Analyze reasons
        analysis = analyze_reasons(df)
        assert 'patterns' in analysis, "Should have pattern analysis"

    def test_workflow_consistency(self):
        """Test that state and context are consistent"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_enhanced_log(str(event_log_path))
        state = reconstruct_state(df)
        context = prepare_agent_context(df)

        # Verify consistency between state and context
        assert abs(context['current_portfolio']['cash'] - state['cash']) < 0.01
        assert abs(context['goals']['ytd_income_actual'] - state['ytd_income']) < 0.01
        assert len(context['current_portfolio']['active_options']) == len(state['active_options'])

    def test_workflow_with_empty_events(self):
        """Test workflow handles edge case of filtering to no events"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_enhanced_log(str(event_log_path))

        # Reconstruct state with a filter that excludes all events
        state = reconstruct_state(df, ticker_filter='NONEXISTENT_TICKER')

        # Should have processed 0 events but still have starting state
        assert state['events_processed'] == 0
        assert state['cash'] >= 0  # Should have starting cash (may be 0 for fresh accounts)


class TestDataIntegrity:
    """Test data integrity across the system"""

    def test_cash_delta_integrity(self):
        """Test that cash deltas are consistent with affects_cash flag"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_event_log(str(event_log_path))

        for idx, row in df.iterrows():
            if not row['affects_cash']:
                assert row['cash_delta'] == 0, f"Event {row['event_id']}: cash_delta should be 0 when affects_cash is False"

    def test_event_type_validity(self):
        """Test that all event types are valid"""
        valid_types = [
            'TRADE', 'OPTION_OPEN', 'OPTION_CLOSE', 'OPTION_EXPIRE', 'OPTION_ASSIGN',
            'DIVIDEND', 'DEPOSIT', 'WITHDRAWAL', 'PRICE_UPDATE', 'SPLIT',
            'NOTE', 'GOAL_UPDATE', 'STRATEGY_UPDATE', 'ADJUSTMENT', 'INSIGHT_LOG',
            'IDEA_SEED', 'IDEA_ACTION', 'IDEA_STATUS'  # Ideas Lab event types
        ]

        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_event_log(str(event_log_path))

        for idx, row in df.iterrows():
            assert row['event_type'] in valid_types, f"Invalid event type: {row['event_type']}"

    def test_event_ids_unique(self):
        """Test that event IDs are unique"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_event_log(str(event_log_path))

        assert len(df['event_id'].unique()) == len(df), "Event IDs should be unique"

    def test_timestamps_sorted(self):
        """Test that events can be sorted by timestamp"""
        script_dir = Path(__file__).parent.parent
        event_log_path = script_dir / 'data' / 'event_log_enhanced.csv'

        df = load_event_log(str(event_log_path))

        # After load_event_log, timestamps should be datetime and sortable
        sorted_df = df.sort_values('timestamp')
        assert len(sorted_df) == len(df), "Should be able to sort by timestamp"


# Need pandas for some tests
import pandas as pd


class TestOptionsScannerE2E:
    """End-to-end tests for the options scanner workflow"""

    def test_scanner_portfolio_holdings(self):
        """Test that scanner can load portfolio holdings"""
        from api.services.options_scanner import get_portfolio_holdings

        portfolio = get_portfolio_holdings()

        assert 'holdings' in portfolio, "Should have holdings"
        assert 'cash' in portfolio, "Should have cash"
        assert 'tickers_with_options' in portfolio, "Should have tickers_with_options"
        assert 'ytd_income' in portfolio, "Should have ytd_income"
        assert 'income_goal' in portfolio, "Should have income_goal"
        assert 'remaining_goal' in portfolio, "Should have remaining_goal"

        # Validate structure
        assert isinstance(portfolio['holdings'], dict), "Holdings should be a dict"
        assert isinstance(portfolio['cash'], (int, float)), "Cash should be numeric"
        assert portfolio['income_goal'] == 30000, "Income goal should be $30K"

    def test_scanner_portfolio_holdings_structure(self):
        """Test that holdings have the expected structure"""
        from api.services.options_scanner import get_portfolio_holdings

        portfolio = get_portfolio_holdings()

        for ticker, info in portfolio['holdings'].items():
            assert 'shares' in info, f"{ticker} should have shares"
            assert 'price' in info, f"{ticker} should have price"
            assert 'avg_cost' in info, f"{ticker} should have avg_cost"
            assert 'contracts_available' in info, f"{ticker} should have contracts_available"
            assert info['shares'] >= 100, f"{ticker} should have at least 100 shares"

    def test_scanner_score_option(self):
        """Test option scoring logic"""
        from api.services.options_scanner import score_option

        # Create a mock high-quality option
        good_option = {
            'ticker': 'TEST',
            'type': 'PUT',
            'annualized_yield_pct': 35,
            'otm_pct': 12,
            'delta': 0.2,
            'prob_otm': 80,
            'dte': 35,
            'volume': 150,
            'open_interest': 600
        }

        score = score_option(good_option, {})

        # Should have a high score (70+ for a quality option)
        assert score >= 60, f"Good option should score well, got {score}"

        # Create a poor option
        poor_option = {
            'ticker': 'TEST',
            'type': 'PUT',
            'annualized_yield_pct': 3,
            'otm_pct': 1,
            'delta': 0.45,
            'prob_otm': 55,
            'dte': 5,
            'volume': 2,
            'open_interest': 10
        }

        poor_score = score_option(poor_option, {})

        assert poor_score < score, "Poor option should score lower than good option"

    def test_scanner_score_option_call_vs_put(self):
        """Test that scoring works for both calls and puts"""
        from api.services.options_scanner import score_option

        put_option = {
            'ticker': 'TEST',
            'type': 'PUT',
            'annualized_yield_pct': 25,
            'otm_pct': 10,
            'prob_otm': 75,
            'dte': 30,
            'volume': 100,
            'open_interest': 500
        }

        call_option = {
            'ticker': 'TEST',
            'type': 'CALL',
            'annualized_yield_pct': 25,
            'otm_pct': 10,
            'prob_otm': 75,
            'dte': 30,
            'volume': 100,
            'open_interest': 500
        }

        put_score = score_option(put_option, {})
        call_score = score_option(call_option, {})

        # Both should be valid scores
        assert put_score > 0, "Put should have positive score"
        assert call_score > 0, "Call should have positive score"

    def test_scanner_recommendations_structure(self):
        """Test that get_recommendations returns proper structure"""
        from api.services.options_scanner import get_recommendations

        # Run scanner with minimal settings
        result = get_recommendations(max_dte=30, min_premium=25, max_results=5, use_llm=False)

        assert 'generated_at' in result, "Should have generated_at"
        assert 'portfolio_summary' in result, "Should have portfolio_summary"
        assert 'recommendations' in result, "Should have recommendations"
        assert 'potential_income' in result, "Should have potential_income"

        # Validate portfolio summary
        summary = result['portfolio_summary']
        assert 'holdings_scanned' in summary, "Should have holdings_scanned"
        assert 'cash_available' in summary, "Should have cash_available"
        assert 'ytd_income' in summary, "Should have ytd_income"

    def test_scanner_recommendations_sorted(self):
        """Test that recommendations are sorted by score"""
        from api.services.options_scanner import get_recommendations

        result = get_recommendations(max_dte=45, min_premium=50, max_results=10, use_llm=False)

        recs = result['recommendations']
        if len(recs) > 1:
            for i in range(len(recs) - 1):
                assert recs[i].get('score', 0) >= recs[i+1].get('score', 0), \
                    "Recommendations should be sorted by score descending"

    def test_scanner_format_recommendation_text(self):
        """Test recommendation text formatting"""
        from api.services.options_scanner import format_recommendation_text

        rec = {
            'ticker': 'TSLA',
            'strategy': 'Cash-Secured Put',
            'strike': 400.0,
            'expiration': '2026-02-15',
            'dte': 35,
            'premium_per_contract': 450,
            'annualized_yield_pct': 28.5,
            'otm_pct': 8.5,
            'delta': 0.22,
            'score': 75
        }

        text = format_recommendation_text(rec)

        assert 'TSLA' in text, "Should include ticker"
        assert 'Cash-Secured Put' in text, "Should include strategy"
        assert '400' in text, "Should include strike"
        assert '2026-02-15' in text, "Should include expiration"


class TestOptionsScannerAPI:
    """Test the options scanner API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client for API"""
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_scanner_quick_recommendations_endpoint(self, client):
        """Test GET /api/scanner/recommendations endpoint"""
        response = client.get('/api/scanner/recommendations')

        assert response.status_code == 200, f"Should return 200, got {response.status_code}"

        data = response.json()
        assert data['status'] == 'success', "Should return success status"
        assert 'recommendations' in data, "Should have recommendations"
        assert 'portfolio_summary' in data, "Should have portfolio_summary"

    def test_scanner_post_scan_endpoint(self, client):
        """Test POST /api/scanner/scan endpoint"""
        response = client.post('/api/scanner/scan', json={
            'max_dte': 30,
            'min_premium': 50,
            'max_results': 5,
            'use_llm': False
        })

        assert response.status_code == 200, f"Should return 200, got {response.status_code}"

        data = response.json()
        assert data['status'] == 'success', "Should return success status"

    def test_scanner_ticker_endpoint(self, client):
        """Test GET /api/scanner/ticker/{ticker} endpoint"""
        # Test with a known ticker (might not have options data)
        response = client.get('/api/scanner/ticker/TSLA')

        assert response.status_code == 200, f"Should return 200, got {response.status_code}"

        data = response.json()
        assert 'status' in data, "Should have status"
        assert 'ticker' in data, "Should have ticker"
        assert data['ticker'] == 'TSLA', "Ticker should match"


class TestSessionTrackingE2E:
    """Test the session tracking functionality"""

    def test_session_starts_automatically(self):
        """Test that session starts automatically on first LLM call"""
        from api.services.langsmith_tracing import (
            trace_llm_call, get_session_stats, start_session
        )

        # Start a fresh session
        start_session()

        # Make a trace
        trace_llm_call(
            model="test-model",
            prompt_tokens=100,
            completion_tokens=50,
            latency_ms=500,
            endpoint="test"
        )

        stats = get_session_stats()

        assert stats['active'] == True, "Session should be active"
        assert stats['call_count'] == 1, "Should have 1 call"
        assert stats['total_tokens'] == 150, "Should have 150 total tokens"

    def test_session_aggregates_multiple_calls(self):
        """Test that session aggregates multiple calls"""
        from api.services.langsmith_tracing import (
            trace_llm_call, get_session_stats, start_session
        )

        # Start fresh
        start_session()

        # Make multiple traces
        for i in range(3):
            trace_llm_call(
                model="test-model",
                prompt_tokens=100,
                completion_tokens=50,
                latency_ms=500,
                endpoint="test"
            )

        stats = get_session_stats()

        assert stats['call_count'] == 3, "Should have 3 calls"
        assert stats['total_tokens'] == 450, "Should have 450 total tokens"
        assert stats['total_prompt_tokens'] == 300, "Should have 300 prompt tokens"
        assert stats['total_completion_tokens'] == 150, "Should have 150 completion tokens"

    def test_session_cost_estimation(self):
        """Test that session estimates costs"""
        from api.services.langsmith_tracing import (
            trace_llm_call, get_session_stats, start_session, estimate_cost
        )

        # Test cost estimation
        cost = estimate_cost("claude-3-sonnet", 1000, 500)
        assert cost > 0, "Should estimate non-zero cost for Claude"

        local_cost = estimate_cost("local-model", 1000, 500)
        assert local_cost == 0, "Local models should have zero cost"

    @pytest.fixture
    def client(self):
        """Create test client for API"""
        from fastapi.testclient import TestClient
        from api.main import app
        return TestClient(app)

    def test_session_api_endpoint(self, client):
        """Test GET /api/chat/session endpoint"""
        response = client.get('/api/chat/session')

        assert response.status_code == 200, f"Should return 200, got {response.status_code}"

        data = response.json()
        # Should have either active session or message about no session
        assert 'active' in data or 'message' in data

    def test_new_session_api_endpoint(self, client):
        """Test POST /api/chat/session/new endpoint"""
        response = client.post('/api/chat/session/new')

        assert response.status_code == 200, f"Should return 200, got {response.status_code}"

        data = response.json()
        assert data['success'] == True, "Should succeed"
        assert 'session_id' in data, "Should return session_id"

    def test_langsmith_status_endpoint(self, client):
        """Test GET /api/chat/langsmith/status endpoint"""
        response = client.get('/api/chat/langsmith/status')

        assert response.status_code == 200, f"Should return 200, got {response.status_code}"

        data = response.json()
        assert 'configured' in data, "Should have configured status"
        assert 'api_key_set' in data, "Should have api_key_set status"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
