"""
Browser E2E tests for LLM settings page.
Uses server-side Jinja2 rendering - values are embedded in HTML on page load.
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


class TestLLMSettingsPage:
    """Browser tests for LLM settings."""

    def test_page_loads(self, page: Page):
        """Settings page loads."""
        page.goto(f"{BASE_URL}/settings")
        expect(page.get_by_role("heading", name="AI Settings")).to_be_visible()

    def test_textarea_has_json(self, page: Page):
        """Textarea contains JSON on initial load."""
        page.goto(f"{BASE_URL}/settings")
        textarea = page.locator("#llm-json")
        content = textarea.input_value()
        # Should be valid JSON
        parsed = json.loads(content)
        assert "provider" in parsed

    def test_textarea_matches_file(self, page: Page):
        """Textarea values match llm_config.json file."""
        page.goto(f"{BASE_URL}/settings")
        textarea = page.locator("#llm-json")
        browser_json = json.loads(textarea.input_value())
        file_json = json.loads(CONFIG_FILE.read_text())

        assert browser_json["provider"] == file_json["provider"]
        assert browser_json["local_model"] == file_json["local_model"]
        assert browser_json["local_url"] == file_json["local_url"]
        assert browser_json["timeout"] == file_json["timeout"]

    def test_status_shows_provider(self, page: Page):
        """Status bar shows current provider."""
        page.goto(f"{BASE_URL}/settings")
        file_json = json.loads(CONFIG_FILE.read_text())
        provider = file_json["provider"].upper()
        # LLM status is in the AI Settings card
        llm_card = page.locator("text=AI Settings").locator("..").locator("..")
        expect(llm_card.locator(".alert")).to_contain_text(provider)

    def test_status_shows_model(self, page: Page):
        """Status bar shows current model."""
        page.goto(f"{BASE_URL}/settings")
        file_json = json.loads(CONFIG_FILE.read_text())
        if file_json["provider"] == "local":
            model = file_json["local_model"]
        else:
            model = file_json["claude_model"]
        llm_card = page.locator("text=AI Settings").locator("..").locator("..")
        expect(llm_card.locator("code")).to_contain_text(model)

    def test_save_button_exists(self, page: Page):
        """Save button visible."""
        page.goto(f"{BASE_URL}/settings")
        expect(page.get_by_role("button", name="Save")).to_be_visible()

    def test_test_button_exists(self, page: Page):
        """Test Connection button visible."""
        page.goto(f"{BASE_URL}/settings")
        expect(page.get_by_role("button", name="Test Connection")).to_be_visible()

    def test_reload_button_exists(self, page: Page):
        """Reload button visible."""
        page.goto(f"{BASE_URL}/settings")
        expect(page.get_by_role("button", name="Reload")).to_be_visible()

    def test_save_updates_file(self, page: Page, config_backup):
        """Clicking Save writes to llm_config.json."""
        page.goto(f"{BASE_URL}/settings")
        textarea = page.locator("#llm-json")

        # Modify timeout
        content = json.loads(textarea.input_value())
        content["timeout"] = 999
        textarea.fill(json.dumps(content, indent=2))

        # Save
        page.get_by_role("button", name="Save").click()
        page.wait_for_timeout(1000)

        # Verify file
        saved = json.loads(CONFIG_FILE.read_text())
        assert saved["timeout"] == 999

    def test_invalid_json_error(self, page: Page):
        """Invalid JSON shows error."""
        page.goto(f"{BASE_URL}/settings")
        textarea = page.locator("#llm-json")
        textarea.fill("not valid json {{{")
        page.get_by_role("button", name="Save").click()
        expect(page.locator("#llm-msg")).to_contain_text("Invalid JSON")

    def test_test_connection_works(self, page: Page):
        """Test Connection returns result."""
        page.goto(f"{BASE_URL}/settings")
        page.get_by_role("button", name="Test Connection").click()
        page.wait_for_timeout(3000)
        msg = page.locator("#llm-msg")
        text = msg.inner_text()
        assert "Connected" in text or "Failed" in text or "Error" in text

    def test_provider_is_valid(self, page: Page):
        """Provider is local or claude."""
        page.goto(f"{BASE_URL}/settings")
        textarea = page.locator("#llm-json")
        content = json.loads(textarea.input_value())
        assert content["provider"] in ["local", "claude"]

    def test_enabled_is_boolean(self, page: Page):
        """Enabled is boolean."""
        page.goto(f"{BASE_URL}/settings")
        textarea = page.locator("#llm-json")
        content = json.loads(textarea.input_value())
        assert isinstance(content["enabled"], bool)

    def test_timeout_is_number(self, page: Page):
        """Timeout is number."""
        page.goto(f"{BASE_URL}/settings")
        textarea = page.locator("#llm-json")
        content = json.loads(textarea.input_value())
        assert isinstance(content["timeout"], int)
