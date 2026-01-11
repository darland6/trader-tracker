"""
Browser E2E tests for Dashboard LLM settings panel.
Tests the 3D dashboard settings at /dashboard
"""

import pytest
import json
from pathlib import Path
from playwright.sync_api import Page, expect

CONFIG_FILE = Path(__file__).parent.parent / "llm_config.json"
BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def config_backup():
    """Backup config before tests, restore after."""
    backup = None
    if CONFIG_FILE.exists():
        backup = CONFIG_FILE.read_text()
    yield
    if backup:
        CONFIG_FILE.write_text(backup)


class TestDashboardLLMSettings:
    """Browser tests for dashboard LLM settings panel."""

    def test_dashboard_loads(self, page: Page):
        """Dashboard page loads."""
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_timeout(2000)
        expect(page.locator("#right-console")).to_be_visible()

    def test_settings_button_exists(self, page: Page):
        """Settings button exists in controls."""
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_timeout(1000)
        settings_btn = page.locator("button:has-text('SETTINGS')")
        expect(settings_btn).to_be_visible()

    def test_settings_panel_opens(self, page: Page):
        """Clicking settings button opens panel."""
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_timeout(1000)
        page.locator("button:has-text('SETTINGS')").click()
        page.wait_for_timeout(500)
        expect(page.locator("#settings-console")).to_be_visible()

    def test_provider_dropdown_exists(self, page: Page):
        """Provider dropdown exists in settings."""
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_timeout(1000)
        page.locator("button:has-text('SETTINGS')").click()
        page.wait_for_timeout(500)
        expect(page.locator("#llm-provider")).to_be_visible()

    def test_provider_has_options(self, page: Page):
        """Provider dropdown has claude and local options."""
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_timeout(1000)
        page.locator("button:has-text('SETTINGS')").click()
        page.wait_for_timeout(500)
        provider = page.locator("#llm-provider")
        expect(provider.locator("option[value='claude']")).to_be_attached()
        expect(provider.locator("option[value='local']")).to_be_attached()

    def test_settings_load_from_api(self, page: Page):
        """Settings are loaded from API."""
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_timeout(1000)
        page.locator("button:has-text('SETTINGS')").click()
        page.wait_for_timeout(1000)

        # Read file to compare
        file_config = json.loads(CONFIG_FILE.read_text())

        # Check provider matches
        provider = page.locator("#llm-provider")
        expect(provider).to_have_value(file_config["provider"])

    def test_local_model_populated(self, page: Page):
        """Local model field is populated."""
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_timeout(1000)
        page.locator("button:has-text('SETTINGS')").click()
        page.wait_for_timeout(1000)

        file_config = json.loads(CONFIG_FILE.read_text())

        # If provider is local, check local-model
        if file_config["provider"] == "local":
            local_model = page.locator("#local-model")
            expect(local_model).to_have_value(file_config["local_model"])

    def test_local_url_populated(self, page: Page):
        """Local URL field is populated."""
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_timeout(1000)
        page.locator("button:has-text('SETTINGS')").click()
        page.wait_for_timeout(1000)

        file_config = json.loads(CONFIG_FILE.read_text())

        if file_config["provider"] == "local":
            local_url = page.locator("#local-url")
            expect(local_url).to_have_value(file_config["local_url"])

    def test_save_button_exists(self, page: Page):
        """Save button exists."""
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_timeout(1000)
        page.locator("button:has-text('SETTINGS')").click()
        page.wait_for_timeout(500)
        expect(page.locator("button:has-text('Save')")).to_be_visible()

    def test_test_button_exists(self, page: Page):
        """Test button exists."""
        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_timeout(1000)
        page.locator("button:has-text('SETTINGS')").click()
        page.wait_for_timeout(500)
        expect(page.locator("button:has-text('Test')")).to_be_visible()

    def test_no_errors_on_load(self, page: Page):
        """No JavaScript errors on settings load."""
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        page.goto(f"{BASE_URL}/dashboard")
        page.wait_for_timeout(1000)
        page.locator("button:has-text('SETTINGS')").click()
        page.wait_for_timeout(1000)

        # Filter out non-critical errors
        critical_errors = [e for e in errors if "innerHTML" in e or "null" in e]
        assert len(critical_errors) == 0, f"JavaScript errors: {critical_errors}"
