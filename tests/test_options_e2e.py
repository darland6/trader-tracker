"""End-to-end tests for options functionality using Playwright."""

import pytest
from playwright.sync_api import Page, expect
import json
import subprocess


BASE_URL = "http://localhost:8000"

# Track test options created during tests for cleanup
TEST_TICKERS = ['TESTSEL', 'TESTBUY', 'FORMTEST', 'BUYFORM', 'ETEST']


def cleanup_test_events():
    """Remove any test events from the CSV after tests run."""
    script = '''
import pandas as pd
df = pd.read_csv('data/event_log_enhanced.csv')
test_tickers = ['TESTSEL', 'TESTBUY', 'FORMTEST', 'BUYFORM', 'ETEST']
mask = df['data_json'].apply(lambda x: not any(t in str(x) for t in test_tickers))
df = df[mask]
df.to_csv('data/event_log_enhanced.csv', index=False)
'''
    subprocess.run(['./venv/bin/python3', '-c', script], cwd='/Users/cory/projects/trader-tracker')


@pytest.fixture(scope="module")
def browser_context(browser):
    """Create a browser context for the tests."""
    context = browser.new_context()
    yield context
    context.close()
    # Cleanup test events after all tests in module complete
    cleanup_test_events()


@pytest.fixture
def page(browser_context):
    """Create a new page for each test."""
    page = browser_context.new_page()
    yield page
    page.close()


class TestOptionsPage:
    """Tests for the /options page."""

    def test_options_page_loads(self, page: Page):
        """Test that the options page loads successfully."""
        page.goto(f"{BASE_URL}/options")
        expect(page).to_have_title("Options - Portfolio Manager")
        expect(page.locator("h2.card-title").first).to_have_text("Active Options")

    def test_open_option_form_visible(self, page: Page):
        """Test that the Open New Option form is visible."""
        page.goto(f"{BASE_URL}/options")

        # Check form fields exist
        expect(page.locator("#option-action")).to_be_visible()
        expect(page.locator("#option-ticker")).to_be_visible()
        expect(page.locator("#option-strategy")).to_be_visible()
        expect(page.locator("#option-strike")).to_be_visible()
        expect(page.locator("#option-expiration")).to_be_visible()
        expect(page.locator("#option-contracts")).to_be_visible()
        expect(page.locator("#option-premium")).to_be_visible()

    def test_action_select_has_buy_sell(self, page: Page):
        """Test that Action select has BUY and SELL options."""
        page.goto(f"{BASE_URL}/options")

        action_select = page.locator("#option-action")
        expect(action_select).to_be_visible()

        # Check options exist
        options = action_select.locator("option")
        expect(options).to_have_count(2)

        # SELL should be first (default)
        expect(options.first).to_have_attribute("value", "SELL")
        expect(options.last).to_have_attribute("value", "BUY")

    def test_premium_label_changes_with_action(self, page: Page):
        """Test that premium label changes based on action selection."""
        page.goto(f"{BASE_URL}/options")

        premium_label = page.locator("#premium-label")

        # Default (SELL) should say "Received"
        expect(premium_label).to_contain_text("Received")

        # Change to BUY
        page.select_option("#option-action", "BUY")
        expect(premium_label).to_contain_text("Paid")

        # Change back to SELL
        page.select_option("#option-action", "SELL")
        expect(premium_label).to_contain_text("Received")

    def test_strategy_select_has_put_call(self, page: Page):
        """Test that Strategy select has Put and Call options."""
        page.goto(f"{BASE_URL}/options")

        strategy_select = page.locator("#option-strategy")
        options = strategy_select.locator("option")
        expect(options).to_have_count(2)

        # Check values
        expect(options.first).to_have_attribute("value", "Put")
        expect(options.last).to_have_attribute("value", "Call")


class TestOptionsAPI:
    """Tests for the options API endpoints."""

    def test_open_option_api_requires_action(self, page: Page):
        """Test that opening an option without action fails."""
        response = page.request.post(
            f"{BASE_URL}/api/options/open",
            data=json.dumps({
                "ticker": "TEST",
                # Missing: action
                "strategy": "Put",
                "strike": 50.0,
                "expiration": "2026-03-20",
                "contracts": 1,
                "premium": 100.0
            }),
            headers={"Content-Type": "application/json"}
        )

        assert response.status == 422  # Validation error

    def test_open_option_api_validates_action(self, page: Page):
        """Test that action must be BUY or SELL."""
        response = page.request.post(
            f"{BASE_URL}/api/options/open",
            data=json.dumps({
                "ticker": "TEST",
                "action": "INVALID",  # Invalid action
                "strategy": "Put",
                "strike": 50.0,
                "expiration": "2026-03-20",
                "contracts": 1,
                "premium": 100.0
            }),
            headers={"Content-Type": "application/json"}
        )

        assert response.status == 422  # Validation error

    def test_open_sell_option_api(self, page: Page):
        """Test successfully opening a SELL option."""
        response = page.request.post(
            f"{BASE_URL}/api/options/open",
            data=json.dumps({
                "ticker": "TESTSEL",
                "action": "SELL",
                "strategy": "Put",
                "strike": 45.0,
                "expiration": "2026-06-20",
                "contracts": 2,
                "premium": 500.0,
                "reason": "Test sell option"
            }),
            headers={"Content-Type": "application/json"}
        )

        assert response.status == 200
        data = response.json()
        assert data["success"] is True
        assert "SELL" in data["message"]
        assert data["data"]["action"] == "SELL"
        assert data["data"]["ticker"] == "TESTSEL"
        assert data["data"]["premium"] == 500.0

    def test_open_buy_option_api(self, page: Page):
        """Test successfully opening a BUY option."""
        response = page.request.post(
            f"{BASE_URL}/api/options/open",
            data=json.dumps({
                "ticker": "TESTBUY",
                "action": "BUY",
                "strategy": "Call",
                "strike": 100.0,
                "expiration": "2026-06-20",
                "contracts": 1,
                "premium": 250.0,
                "reason": "Test buy option"
            }),
            headers={"Content-Type": "application/json"}
        )

        assert response.status == 200
        data = response.json()
        assert data["success"] is True
        assert "BUY" in data["message"]
        assert data["data"]["action"] == "BUY"

    def test_get_active_options_api(self, page: Page):
        """Test getting active options includes action field."""
        response = page.request.get(f"{BASE_URL}/api/options/active")

        assert response.status == 200
        data = response.json()
        assert "options" in data

        # Check that options have action field
        for opt in data["options"]:
            assert "action" in opt, f"Option missing action field: {opt}"
            assert opt["action"] in ["BUY", "SELL"], f"Invalid action: {opt['action']}"


class TestOptionsForm:
    """Tests for the options form submission."""

    def test_submit_sell_option_form(self, page: Page):
        """Test submitting a SELL option through the form."""
        page.goto(f"{BASE_URL}/options")

        # Fill in the form
        page.select_option("#option-action", "SELL")
        page.fill("#option-ticker", "FORMTEST")
        page.select_option("#option-strategy", "Put")
        page.fill("#option-strike", "35")
        page.fill("#option-expiration", "2026-07-17")
        page.fill("#option-contracts", "3")
        page.fill("#option-premium", "750")
        page.fill("#option-reason", "Testing form submission")

        # Submit the form (use the specific form's submit button)
        page.locator("#option-form button[type='submit']").click()

        # Wait for success message
        expect(page.locator("#option-result .alert-success")).to_be_visible(timeout=5000)

    def test_submit_buy_option_form(self, page: Page):
        """Test submitting a BUY option through the form."""
        page.goto(f"{BASE_URL}/options")

        # Fill in the form
        page.select_option("#option-action", "BUY")
        page.fill("#option-ticker", "BUYFORM")
        page.select_option("#option-strategy", "Call")
        page.fill("#option-strike", "150")
        page.fill("#option-expiration", "2026-08-21")
        page.fill("#option-contracts", "1")
        page.fill("#option-premium", "300")
        page.fill("#option-reason", "Testing buy form")

        # Submit (use the specific form's submit button)
        page.locator("#option-form button[type='submit']").click()

        # Wait for success
        expect(page.locator("#option-result .alert-success")).to_be_visible(timeout=5000)

    def test_form_validation_required_fields(self, page: Page):
        """Test that form validates required fields."""
        page.goto(f"{BASE_URL}/options")

        # Try to submit empty form (use the specific form's submit button)
        page.locator("#option-form button[type='submit']").click()

        # Form should not submit (HTML5 validation)
        # Check that we're still on the same page with no result
        expect(page.locator("#option-result")).to_be_empty()


class TestActiveOptionsTable:
    """Tests for the active options table display."""

    def test_active_options_shows_action_column(self, page: Page):
        """Test that active options table has Action column."""
        page.goto(f"{BASE_URL}/options")

        # Check table headers
        headers = page.locator("table thead th")
        header_texts = [h.inner_text() for h in headers.all()]

        assert "Action" in header_texts, f"Action column missing. Headers: {header_texts}"

    def test_sell_options_show_negative_contracts(self, page: Page):
        """Test that SELL options show negative contract count (like Schwab)."""
        page.goto(f"{BASE_URL}/options")

        # Find a SELL option row (badge with text SELL)
        sell_badges = page.locator("span.badge:has-text('SELL')")

        if sell_badges.count() > 0:
            # Get the row containing the SELL badge
            row = sell_badges.first.locator("xpath=ancestor::tr")
            # Get the contracts cell (7th column, index 6)
            contracts_cell = row.locator("td").nth(6)
            contracts_text = contracts_cell.inner_text()

            # Should start with "-" for SELL
            assert contracts_text.startswith("-"), f"SELL contracts should be negative: {contracts_text}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
